from datetime import datetime, timedelta

from app.queue.job_queue import enqueue_unique
from app.db.sqlite import get_session, Campaign, Lead

TICK_SECONDS = 15
POLL_REPLIES_SECONDS = 60  # poll once a minute for MVP


def handle_tick(payload: dict):
    """
    Periodically enqueue work for running campaigns.
    Uses enqueue_unique() to avoid job storms.
    """

    now = datetime.utcnow()

    session = get_session()
    try:
        campaigns = session.query(Campaign).filter(Campaign.status == "running").all()

        for c in campaigns:
            # 1) poll replies (throttled + deduped)
            enqueue_unique(
                "poll_replies",
                {"campaign_id": c.id},
                run_at=now,
                dedupe_window_seconds=POLL_REPLIES_SECONDS,
            )

            # 2) generate copy for due leads (deduped per lead)
            due_leads = (
                session.query(Lead)
                .filter(Lead.campaign_id == c.id)
                .filter(Lead.next_touch_at <= now)
                .filter(Lead.state.in_(["NEW", "FOLLOWUP"]))
                .limit(25)
                .all()
            )

            for lead in due_leads:
                enqueue_unique(
                    "generate_copy",
                    {"campaign_id": c.id, "lead_id": lead.id},
                    run_at=now,
                    # keep this generous so you don't regenerate constantly
                    dedupe_window_seconds=6 * 3600,  # 6 hours (tune later)
                )

    finally:
        session.close()

    # 3) schedule next tick (deduped; current running tick won't block this)
    enqueue_unique(
        "tick",
        {},
        run_at=(now + timedelta(seconds=TICK_SECONDS)),
        dedupe_window_seconds=TICK_SECONDS * 2,
    )
