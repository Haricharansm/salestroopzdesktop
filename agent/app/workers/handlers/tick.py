# app/workers/handlers/tick.py

from datetime import datetime, timedelta
from app.queue.job_queue import enqueue
from app.db.sqlite import get_session, Campaign, Lead, log_event

TICK_EVERY_SECONDS = 15
POLL_REPLIES_EVERY_SECONDS = 60

def handle_tick(payload: dict):
    session = get_session()
    now = datetime.utcnow()

    campaigns = session.query(Campaign).filter(Campaign.status == "running").all()

    for c in campaigns:
        # Skip if no leads
        due_leads = (
            session.query(Lead)
            .filter(Lead.campaign_id == c.id)
            .filter(Lead.next_touch_at <= now)
            .filter(Lead.state.in_(["NEW", "FOLLOWUP"]))
            .filter(Lead.touch_count < (c.max_touches or 4))
            .limit(25)
            .all()
        )

        for lead in due_leads:
            enqueue("generate_copy", {"campaign_id": c.id, "lead_id": lead.id})

        # poll replies (separate loop)
        enqueue("poll_replies", {"campaign_id": c.id}, run_at=now + timedelta(seconds=POLL_REPLIES_EVERY_SECONDS))

    session.close()

    log_event("runner.heartbeat", message="tick scheduled next")

    # schedule next tick
    enqueue("tick", {}, run_at=(datetime.utcnow() + timedelta(seconds=TICK_EVERY_SECONDS)))
