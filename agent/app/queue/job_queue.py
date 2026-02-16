# app/queue/job_queue.py

import json
import os
import socket
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.exc import OperationalError

from app.db.sqlite import get_session, JobQueue, log_event

LEASE_SECONDS_DEFAULT = 60


def _owner_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _extract_campaign_lead(payload: dict) -> tuple[int | None, int | None]:
    campaign_id = payload.get("campaign_id")
    lead_id = payload.get("lead_id")

    if campaign_id is None:
        campaign = payload.get("campaign") or {}
        campaign_id = campaign.get("id")

    if lead_id is None:
        lead = payload.get("lead") or {}
        lead_id = lead.get("id")

    try:
        campaign_id = int(campaign_id) if campaign_id is not None else None
    except Exception:
        campaign_id = None

    try:
        lead_id = int(lead_id) if lead_id is not None else None
    except Exception:
        lead_id = None

    return campaign_id, lead_id


def enqueue(job_type: str, payload: dict, run_at: datetime | None = None, max_attempts: int = 8) -> int:
    session = get_session()
    row = JobQueue(
        job_type=job_type,
        status="queued",
        run_at=run_at or datetime.utcnow(),
        attempts=0,
        max_attempts=max_attempts,

        # ✅ important for dedupe / visibility:
        campaign_id=payload.get("campaign_id"),
        lead_id=payload.get("lead_id"),

        payload_json=json.dumps(payload),
        updated_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    session.close()
    return row.id


        log_event(
            "job.enqueued",
            job_id=row.id,
            campaign_id=row.campaign_id,
            lead_id=row.lead_id,
            message=f"Enqueued {row.job_type}",
            data={"run_at": row.run_at.isoformat()},
        )
        return row.id
    finally:
        session.close()


def claim_next_job(lease_seconds: int = LEASE_SECONDS_DEFAULT) -> JobQueue | None:
    """
    Claim the next due job by taking a lease.
    Crash-safe:
    - jobs stuck in running can be reclaimed after lease expires
    """
    now = datetime.utcnow()
    owner = _owner_id()
    lease_expires = now + timedelta(seconds=lease_seconds)

    session = get_session()
    try:
        # 1) Find a candidate job id
        candidate = (
            session.query(JobQueue.id)
            .filter(JobQueue.run_at <= now)
            .filter(JobQueue.status.in_(["queued", "running"]))
            .filter(or_(JobQueue.lease_expires_at == None, JobQueue.lease_expires_at <= now))
            .order_by(JobQueue.run_at.asc(), JobQueue.id.asc())
            .first()
        )

        if not candidate:
            return None

        job_id = candidate[0]

        # 2) Try to claim it "atomically" (conditional update)
        updated = (
            session.query(JobQueue)
            .filter(JobQueue.id == job_id)
            .filter(JobQueue.run_at <= now)
            .filter(JobQueue.status.in_(["queued", "running"]))
            .filter(or_(JobQueue.lease_expires_at == None, JobQueue.lease_expires_at <= now))
            .update(
                {
                    JobQueue.status: "running",
                    JobQueue.lease_owner: owner,
                    JobQueue.lease_expires_at: lease_expires,
                    JobQueue.updated_at: now,
                },
                synchronize_session=False,
            )
        )

        session.commit()

        if updated == 0:
            return None

        # 3) Re-read the claimed job
        job = session.query(JobQueue).filter(JobQueue.id == job_id).first()
        if job:
            log_event(
                "job.claimed",
                job_id=job.id,
                campaign_id=job.campaign_id,
                lead_id=job.lead_id,
                message=f"Claimed {job.job_type}",
                data={"owner": owner, "lease_expires_at": lease_expires.isoformat()},
            )

        return job

    except OperationalError as e:
        session.rollback()
        log_event("job.claim_error", level="WARN", message=str(e))
        return None

    finally:
        session.close()


def mark_done(job_id: int):
    session = get_session()
    try:
        job = session.query(JobQueue).filter(JobQueue.id == job_id).first()
        if not job:
            return

        job.status = "done"
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = datetime.utcnow()

        session.commit()

        log_event(
            "job.done",
            job_id=job_id,
            campaign_id=job.campaign_id,
            lead_id=job.lead_id,
        )
    finally:
        session.close()


def mark_failed(job_id: int, err: str, retry_at: datetime | None):
    session = get_session()
    try:
        job = session.query(JobQueue).filter(JobQueue.id == job_id).first()
        if not job:
            return

        job.attempts = (job.attempts or 0) + 1
        job.last_error = err
        job.updated_at = datetime.utcnow()
        job.lease_owner = None
        job.lease_expires_at = None

        if job.attempts >= (job.max_attempts or 8):
            job.status = "failed"
            session.commit()
            log_event(
                "job.failed",
                level="ERROR",
                job_id=job_id,
                campaign_id=job.campaign_id,
                lead_id=job.lead_id,
                message=err,
                data={"attempts": job.attempts},
            )
            return

        job.status = "queued"
        job.run_at = retry_at or (datetime.utcnow() + timedelta(seconds=10))
        session.commit()

        log_event(
            "job.retry_scheduled",
            level="WARN",
            job_id=job_id,
            campaign_id=job.campaign_id,
            lead_id=job.lead_id,
            message=err,
            data={"attempts": job.attempts, "run_at": job.run_at.isoformat()},
        )
    finally:
        session.close()
