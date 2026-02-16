# app/workers/handlers/send_email.py

from datetime import datetime, timedelta

from app.db.sqlite import (
    get_session,
    Campaign,
    Lead,
    OutboxEmail,
    log_event,
    log_activity,
)
from app.m365.auth import M365Auth
from app.m365.client import M365Client


def handle_send_email(payload: dict):
    outbox_id = int(payload["outbox_id"])
    campaign_id = int(payload.get("campaign_id") or 0) or None
    lead_id = int(payload.get("lead_id") or 0) or None

    session = get_session()
    try:
        row = session.query(OutboxEmail).filter(OutboxEmail.id == outbox_id).first()
        if not row:
            log_event("email.skip", level="WARN", campaign_id=campaign_id, lead_id=lead_id, message="missing outbox row")
            return

        if row.status == "sent":
            log_event("email.idempotent", campaign_id=row.campaign_id, lead_id=row.lead_id, message="already sent", data={"outbox_id": row.id})
            return

        c = session.query(Campaign).filter(Campaign.id == row.campaign_id).first()
        lead = session.query(Lead).filter(Lead.id == row.lead_id).first()
        if not c or not lead:
            log_event("email.skip", level="WARN", campaign_id=row.campaign_id, lead_id=row.lead_id, message="missing campaign/lead")
            return

        if c.status != "running":
            log_event("email.skip", campaign_id=c.id, lead_id=lead.id, message=f"campaign not running ({c.status})")
            return

        # Acquire token (must already be connected via device flow in UI)
        auth = M365Auth()
        token = auth.acquire_token_silent()
        if not token or "access_token" not in token:
            raise RuntimeError("Not connected to Microsoft 365 (no token). Go to Settings (M365) and connect.")

        client = M365Client(token["access_token"])

        # Basic personalization tokens (keep it simple)
        first_name = (lead.full_name or "").split(" ")[0].strip() or "there"
        subject = row.subject.replace("{{first_name}}", first_name)
        body = row.body.replace("{{first_name}}", first_name)

        # NOTE: your M365Client.send_mail currently doesn't return message id.
        # If you later return message-id/thread-id, store it in provider_message_id/thread_id.
        client.send_mail(lead.email, subject, body)

        row.status = "sent"
        row.sent_at = datetime.utcnow()
        row.last_error = None

        # advance lead
        lead.touch_count = int(lead.touch_count or 0) + 1
        lead.state = "WAITING_REPLY"
        lead.next_touch_at = datetime.utcnow() + timedelta(days=int(c.cadence_days or 3))

        session.commit()

        log_activity(lead.id, "email_sent", f"Sent step {row.step_index}: {subject}")
        log_event("email.sent", campaign_id=c.id, lead_id=lead.id, message="sent", data={"outbox_id": row.id, "step_index": row.step_index})

    except Exception as e:
        # mark outbox failed (so the retry will still pick it up; runner will retry job)
        try:
            row = session.query(OutboxEmail).filter(OutboxEmail.id == outbox_id).first()
            if row:
                row.status = "failed"
                row.last_error = str(e)
                session.commit()
        except Exception:
            session.rollback()

        log_event("email.error", level="ERROR", campaign_id=campaign_id, lead_id=lead_id, message=str(e))
        raise

    finally:
        session.close()
