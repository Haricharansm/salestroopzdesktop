# app/workers/handlers/poll_replies.py

from app.db.sqlite import log_event

def handle_poll_replies(payload: dict):
    campaign_id = int(payload.get("campaign_id") or 0) or None

    # TODO: implement:
    # - list recent messages
    # - correlate to lead by thread_id / conversation_id
    # - sentiment/intent classify
    # - stop lead on negative, schedule meeting on positive

    log_event(
        "replies.poll",
        campaign_id=campaign_id,
        message="poll stub (not implemented yet)",
    )

    # IMPORTANT:
    # Do NOT enqueue poll_replies again here.
    # Scheduling is handled by tick via enqueue_unique().
