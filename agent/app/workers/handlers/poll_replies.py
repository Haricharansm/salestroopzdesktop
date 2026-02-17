# app/workers/handlers/poll_replies.py

import json
from datetime import datetime, timedelta

from app.db.sqlite import (
    get_session,
    Lead,
    InboxMessage,
    log_event,
    log_activity,
)
from app.queue.job_queue import enqueue_unique
from app.m365.auth import M365Auth
from app.m365.client import M365Client


def extract_from_email(m: dict) -> str:
    frm = (m.get("from") or {}).get("emailAddress") or {}
    return (frm.get("address") or "").strip().lower()


def parse_dt(_iso: str | None) -> datetime | None:
    if not _iso:
        return None
    try:
        # Graph often: 2026-02-17T12:34:56Z
        s = _iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except Exception:
        return None


def handle_poll_replies(payload: dict):
    campaign_id = payload.get("campaign_id")
    campaign_id = int(campaign_id) if campaign_id is not None else None

    # 1) Acquire token
    token = M365Auth().acquire_token_silent()
    if not token or "access_token" not in token:
        raise RuntimeError("Not connected to Microsoft 365 (no token). Go to Settings (M365) and connect.")

    client = M365Client(token["access_token"])

    # 2) Fetch recent inbox messages (last 10 minutes)
    since = (datetime.utcnow() - timedelta(minutes=10)).isoformat() + "Z"
    resp = client.list_inbox_since(since_iso=since, top=50)
    messages = resp.get("value", []) if isinstance(resp, dict) else []

    session = get_session()
    inserted = 0
    try:
        for m in messages:
            provider_message_id = (m.get("id") or "").strip()
            if not provider_message_id:
                continue

            # 3) Dedupe
            exists = (
                session.query(InboxMessage)
                .filter(InboxMessage.provider_message_id == provider_message_id)
                .first()
            )
            if exists:
                continue

            from_email = extract_from_email(m)
            if not from_email:
                continue

            # 4) Correlate lead (MVP: by sender email)
            lead = session.query(Lead).filter(Lead.email == from_email).first()
            if not lead:
                continue

            # Optional campaign filter
            if campaign_id and lead.campaign_id != campaign_id:
                continue

            received_at = parse_dt(m.get("receivedDateTime")) or datetime.utcnow()
            subject = (m.get("subject") or "").strip()
            body_preview = (m.get("bodyPreview") or "").strip()
            thread_id = m.get("conversationId")

            # 5) Store InboxMessage
            im = InboxMessage(
                provider="m365",
                campaign_id=lead.campaign_id,
                lead_id=lead.id,
                from_email=from_email,
                subject=subject,
                provider_message_id=provider_message_id,
                thread_id=thread_id,
                received_at=received_at,
                body_preview=body_preview,
                body_text=body_preview,  # MVP
                raw_json=json.dumps(m),
                processed=0,
            )
            session.add(im)
            session.commit()
            session.refresh(im)
            inserted += 1

            # 6) Log + enqueue decide_next
            preview = (im.body_preview or "")[:120]
            log_activity(lead.id, "reply_received", f"Reply: {preview}")
            log_event("reply.received", campaign_id=lead.campaign_id, lead_id=lead.id, message="reply stored")

            enqueue_unique(
                "decide_next",
                {"campaign_id": lead.campaign_id, "lead_id": lead.id, "inbox_message_id": im.id},
                run_at=datetime.utcnow(),
                dedupe_window_seconds=60,
            )

        log_event(
            "replies.poll",
            campaign_id=campaign_id,
            message=f"poll completed, inserted={inserted}",
            data={"inserted": inserted, "window_minutes": 10, "fetched": len(messages)},
        )
    finally:
        session.close()

    # IMPORTANT: do NOT enqueue poll_replies here.
    # tick schedules it using enqueue_unique().
