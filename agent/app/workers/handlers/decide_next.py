import re
from datetime import datetime, timedelta
from app.db.sqlite import get_session, Lead, InboxMessage, LeadDecision, log_event, log_activity
from app.queue.job_queue import enqueue_unique

NEG = ["not interested", "no thanks", "don't contact", "stop", "do not email"]
UNSUB = ["unsubscribe", "remove me", "opt out"]
POS = ["interested", "let's talk", "call", "meeting", "schedule", "demo"]
OOO = ["out of office", "ooo", "vacation", "back on"]

def _contains(text, phrases):
    t = (text or "").lower()
    return any(p in t for p in phrases)

def handle_decide_next(payload: dict):
    lead_id = int(payload["lead_id"])
    inbox_id = int(payload["inbox_message_id"])

    session = get_session()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        msg = session.query(InboxMessage).filter(InboxMessage.id == inbox_id).first()
        if not lead or not msg:
            return

        if msg.processed == 1:
            return

        text = (msg.body_text or msg.body_preview or "").strip()

        decision = "NEUTRAL"
        confidence = 60
        rationale = ""

        if _contains(text, UNSUB):
            decision, confidence, rationale = "UNSUB", 95, "unsubscribe keyword"
            lead.state = "STOPPED_NEGATIVE"

        elif _contains(text, NEG):
            decision, confidence, rationale = "NEGATIVE", 85, "negative keyword"
            lead.state = "STOPPED_NEGATIVE"

        elif _contains(text, OOO):
            decision, confidence, rationale = "OOO", 80, "out-of-office keyword"
            lead.state = "FOLLOWUP"
            lead.next_touch_at = datetime.utcnow() + timedelta(days=7)

        elif _contains(text, POS):
            decision, confidence, rationale = "MEETING", 85, "positive keyword"
            lead.state = "STOPPED_POSITIVE"

        else:
            # neutral reply: keep in waiting, or schedule follow-up
            decision, confidence, rationale = "NEUTRAL", 55, "no keywords"
            lead.state = "WAITING_REPLY"
            # optional: push next touch out a bit
            lead.next_touch_at = datetime.utcnow() + timedelta(days=3)

        # record decision
        d = LeadDecision(
            lead_id=lead.id,
            campaign_id=lead.campaign_id,
            decision=decision,
            confidence=confidence,
            rationale=rationale,
        )
        session.add(d)

        msg.processed = 1
        session.commit()

        log_activity(lead.id, "decision", f"decide_next: {decision} ({confidence}%)")
        log_event("decide_next.done", campaign_id=lead.campaign_id, lead_id=lead.id, message=decision)

        # Optional: if MEETING, enqueue a notification job or create a “task”
        # enqueue_unique("notify_user", {...}, run_at=datetime.utcnow(), dedupe_window_seconds=60)

    finally:
        session.close()
