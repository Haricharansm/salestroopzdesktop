# app/workers/handlers/poll_replies.py

from app.db.sqlite import log_event

def handle_poll_replies(payload):
    campaign_id = payload.get("campaign_id")
    token = M365Auth().acquire_token_silent()
    client = M365Client(token["access_token"])

    messages = client.list_recent_inbox_messages(minutes=10, top=50)

    session = get_session()
    try:
        for m in messages:
            # 1) dedupe by provider_message_id
            if session.query(InboxMessage).filter(InboxMessage.provider_message_id == m["id"]).first():
                continue

            from_email = extract_from_email(m)
            lead = session.query(Lead).filter(Lead.email == from_email).first()
            if not lead:
                continue

            # optional: filter by campaign_id if provided
            if campaign_id and lead.campaign_id != int(campaign_id):
                continue

            im = InboxMessage(
                provider="m365",
                campaign_id=lead.campaign_id,
                lead_id=lead.id,
                from_email=from_email,
                subject=m.get("subject"),
                provider_message_id=m["id"],
                thread_id=m.get("conversationId"),
                received_at=parse_dt(m.get("receivedDateTime")),
                body_preview=m.get("bodyPreview"),
                body_text=html_to_text(m.get("body", {}).get("content", "")),
                raw_json=json.dumps(m),
                processed=0,
            )
            session.add(im)
            session.commit()

            log_activity(lead.id, "reply_received", f"Reply: {im.body_preview[:120]}")
            log_event("reply.received", campaign_id=lead.campaign_id, lead_id=lead.id, message="reply stored")

            enqueue_unique(
                "decide_next",
                {"campaign_id": lead.campaign_id, "lead_id": lead.id, "inbox_message_id": im.id},
                run_at=datetime.utcnow(),
                dedupe_window_seconds=60,
            )
    finally:
        session.close()

 # TODO: implement:
    # - list recent messages
    # - correlate to lead by thread_id / conversation_id
    # - sentiment/intent classify
    # - stop lead on negative, schedule meeting on positive

    # IMPORTANT:
    # Do NOT enqueue poll_replies again here.
    # Scheduling is handled by tick via enqueue_unique().
