# app/workers/handlers/generate_copy.py

import json
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.db.sqlite import (
    get_session,
    Campaign,
    Lead,
    OutboxEmail,
    log_event,
)
from app.queue.job_queue import enqueue
from app.llm.ollama_client import generate_json


def _step_index_for_lead(lead: Lead) -> int:
    return int(lead.touch_count or 0)


def _campaign_context(c: Campaign) -> dict:
    strategy = json.loads(c.strategy_json or "{}")
    sequence = json.loads(c.sequence_json or "{}")
    run_cfg = json.loads(c.run_config_json or "{}")
    return {"strategy": strategy, "sequence": sequence, "run_config": run_cfg}


def _prompt_email_copy(ctx: dict, lead: Lead, step_index: int) -> str:
    """
    Keep prompts small for 3B–7B.
    JSON-only output.
    """
    strategy = ctx["strategy"]
    sequence = ctx["sequence"]
    steps = sequence.get("steps") or []
    step = steps[step_index] if step_index < len(steps) else {}

    return f"""
You are an AI SDR. Write ONE outreach email.

Return STRICT JSON:
{{
  "subject": "...",
  "body": "..."
}}

Context:
- Positioning: {json.dumps(strategy.get("positioning", {}))}
- Messaging: {json.dumps(strategy.get("messaging", {}))}
- Step {step_index}: {json.dumps(step)}
- Lead: {json.dumps({"full_name": lead.full_name, "email": lead.email, "company": lead.company})}

Rules:
- Keep it short and human (<=120 words)
- Use {{first_name}} token if you want personalization
- No markdown
""".strip()


def handle_generate_copy(payload: dict):
    campaign_id = int(payload["campaign_id"])
    lead_id = int(payload["lead_id"])

    session = get_session()
    try:
        c = session.query(Campaign).filter(Campaign.id == campaign_id).first()
        lead = session.query(Lead).filter(Lead.id == lead_id).first()

        if not c or not lead:
            log_event("copy.skip", level="WARN", campaign_id=campaign_id, lead_id=lead_id, message="missing campaign/lead")
            return

        if c.status != "running":
            log_event("copy.skip", campaign_id=c.id, lead_id=lead.id, message=f"campaign not running ({c.status})")
            return

        if lead.state not in ("NEW", "FOLLOWUP"):
            log_event("copy.skip", campaign_id=c.id, lead_id=lead.id, message=f"lead state {lead.state}")
            return

        if (lead.touch_count or 0) >= (c.max_touches or 4):
            lead.state = "COMPLETED"
            session.commit()
            log_event("lead.completed", campaign_id=c.id, lead_id=lead.id, message="max touches reached")
            return

        step_index = _step_index_for_lead(lead)
        dedupe_key = f"{c.id}:{lead.id}:{step_index}"

        # If outbox already exists, do not regenerate.
        existing = session.query(OutboxEmail).filter(OutboxEmail.dedupe_key == dedupe_key).first()
        if existing:
            if existing.status == "queued":
                enqueue("send_email", {"outbox_id": existing.id, "campaign_id": c.id, "lead_id": lead.id})
            log_event("copy.exists", campaign_id=c.id, lead_id=lead.id, message="outbox already exists", data={"outbox_id": existing.id})
            return

        ctx = _campaign_context(c)
        prompt = _prompt_email_copy(ctx, lead, step_index)

        copy = generate_json(prompt, num_predict=220)  # small models friendly
        subject = (copy.get("subject") or "").strip() or "Quick question"
        body = (copy.get("body") or "").strip() or "Hi {{first_name}}, quick question..."

        row = OutboxEmail(
            campaign_id=c.id,
            lead_id=lead.id,
            step_index=step_index,
            dedupe_key=dedupe_key,
            subject=subject,
            body=body,
            status="queued",
            provider="m365",
            created_at=datetime.utcnow(),
        )
        session.add(row)

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # Another worker created it first; safe to exit.
            log_event("copy.race", level="WARN", campaign_id=c.id, lead_id=lead.id, message="dedupe hit")
            return

        session.refresh(row)
        log_event("copy.generated", campaign_id=c.id, lead_id=lead.id, message="outbox created", data={"outbox_id": row.id})

        enqueue("send_email", {"outbox_id": row.id, "campaign_id": c.id, "lead_id": lead.id})

    finally:
        session.close()
