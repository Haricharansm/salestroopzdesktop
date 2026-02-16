# app/workers/handlers/poll_replies.py

from datetime import datetime, timedelta
from app.db.sqlite import log_event
from app.queue.job_queue import enqueue

def handle_poll_replies(payload: dict):
    campaign_id = payload.get("campaign_id")
    # TODO: implement:
    # - list recent messages
    # - correlate to lead by thread_id / conversation_id
    # - sentiment/intent classify
    # - stop lead on negative, schedule meeting on positive

    log_event("replies.poll", campaign_id=campaign_id, message="poll stub (not implemented yet)")

    # keep polling
    enqueue("poll_replies", {"campaign_id": campaign_id}, run_at=datetime.utcnow() + timedelta(seconds=60))
