from datetime import datetime, timedelta
from sqlalchemy import func

from app.queue.job_queue import enqueue
from app.db.sqlite import get_session, Campaign, Lead, JobQueue


TICK_SECONDS = 15
POLL_REPLIES_SECONDS = 60   # don't poll every tick; 60s is fine for MVP


def handle_tick(payload: dict):
    """
    Periodically enqueue work for running campaigns.
    SAFETY:
    - schedule next tick only if none pending
    - poll_replies only if none pending for campaign AND not too frequent
    - generate_copy only if none pending for that lead
    """
    session = get_session()
    now = datetime.utcnow()

    campaigns = session.query(Campaign).filter(Campaign.status == "running").all()

    for c in campaigns:
        # ----------------------------
        # 1) poll replies (deduped + throttled)
        # ----------------------------
        pending_poll = (
            session.query(func.count(JobQueue.id))
            .filter(JobQueue.job_type == "poll_replies")
            .filter(JobQueue.campaign_id == c.id)
            .filter(JobQueue.status.in_(["queued", "running"]))
            .scalar()
        ) or 0

        if pending_poll == 0:
            # additionally: don't enqueue if we just did it recently
            last_poll_done = (
                session.query(JobQueue)
                .filter(JobQueue.job_type == "poll_replies")
                .filter(JobQueue.campaign_id == c.id)
                .filter(JobQueue.status == "done")
                .order_by(JobQueue.id.desc())
                .first()
            )
            if not last_poll_done or (last_poll_done.updated_at and (now - last_poll_done.updated_at).total_seconds() >= POLL_REPLIES_SECONDS):
                enqueue("poll_replies", {"campaign_id": c.id})

        # ----------------------------
        # 2) generate copy for due leads (deduped per lead)
        # ----------------------------
        due_leads = (
            session.query(Lead)
            .filter(Lead.campaign_id == c.id)
            .filter(Lead.next_touch_at <= now)
            .filter(Lead.state.in_(["NEW", "FOLLOWUP"]))
            .limit(25)
            .all()
        )

        for lead in due_leads:
            pending_copy = (
                session.query(func.count(JobQueue.id))
                .filter(JobQueue.job_type == "generate_copy")
                .filter(JobQueue.campaign_id == c.id)
                .filter(JobQueue.lead_id == lead.id)
                .filter(JobQueue.status.in_(["queued", "running"]))
                .scalar()
            ) or 0

            if pending_copy == 0:
                enqueue("generate_copy", {"campaign_id": c.id, "lead_id": lead.id})

    session.close()

    # ----------------------------
    # 3) singleton tick scheduling
    # ----------------------------
    session2 = get_session()
    pending_tick = (
        session2.query(func.count(JobQueue.id))
        .filter(JobQueue.job_type == "tick")
        .filter(JobQueue.status.in_(["queued", "running"]))
        .scalar()
    ) or 0
    session2.close()

    if pending_tick == 0:
        enqueue("tick", {}, run_at=(datetime.utcnow() + timedelta(seconds=TICK_SECONDS)))
