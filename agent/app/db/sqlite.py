# app/db/sqlite.py

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
import json

DATABASE_URL = "sqlite:///salestroopz.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

# ============================================================
# Core Tables
# ============================================================

# ----------------------------
# Workspace
# ----------------------------
class Workspace(Base):
    __tablename__ = "workspace"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String)
    offering = Column(String)
    icp = Column(String)

    campaigns = relationship("Campaign", back_populates="workspace")


# ----------------------------
# Campaign
# ----------------------------
class Campaign(Base):
    __tablename__ = "campaign"

    id = Column(Integer, primary_key=True, index=True)

    workspace_id = Column(Integer, ForeignKey("workspace.id"))
    name = Column(String)

    status = Column(String, default="draft")
    # draft | running | paused | completed | failed | stopped

    cadence_days = Column(Integer, default=3)
    max_touches = Column(Integer, default=4)

    # Strategy + runner configs (JSON)
    strategy_json = Column(Text, nullable=True)
    sequence_json = Column(Text, nullable=True)
    run_config_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign")


# ----------------------------
# Lead
# ----------------------------
class Lead(Base):
    __tablename__ = "lead"

    id = Column(Integer, primary_key=True, index=True)

    campaign_id = Column(Integer, ForeignKey("campaign.id"))

    full_name = Column(String)
    email = Column(String, index=True)
    company = Column(String)

    state = Column(String, default="NEW")
    # NEW | WAITING_REPLY | FOLLOWUP | STOPPED_POSITIVE | STOPPED_NEGATIVE | COMPLETED

    touch_count = Column(Integer, default=0)
    next_touch_at = Column(DateTime, default=datetime.utcnow)

    conversation_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="leads")
    activities = relationship("ActivityLog", back_populates="lead")


# ----------------------------
# Activity Log (Human-friendly)
# ----------------------------
class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)

    lead_id = Column(Integer, ForeignKey("lead.id"))

    type = Column(String)
    # email_sent | reply_received | followup_scheduled | positive_detected | negative_detected

    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="activities")


# ============================================================
# Runtime Tables (Queue / Outbox / Events)
# ============================================================

# ----------------------------
# Durable Job Queue (SQLite-backed)
# ----------------------------
class JobQueue(Base):
    __tablename__ = "job_queue"

    id = Column(Integer, primary_key=True, index=True)

    # Helpful for filtering / debugging
    campaign_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)

    job_type = Column(String, index=True)                  # tick | generate_copy | send_email | poll_replies
    status = Column(String, default="queued", index=True)  # queued | running | done | failed

    run_at = Column(DateTime, default=datetime.utcnow, index=True)

    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=8)

    lease_owner = Column(String, nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)

    payload_json = Column(Text, nullable=False)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Optional composite index for faster runner scans
Index("ix_job_queue_status_runat", JobQueue.status, JobQueue.run_at)

# ----------------------------
# Outbox (Idempotent sending)
# ----------------------------
class OutboxEmail(Base):
    __tablename__ = "outbox_email"

    id = Column(Integer, primary_key=True, index=True)

    campaign_id = Column(Integer, ForeignKey("campaign.id"), index=True)
    lead_id = Column(Integer, ForeignKey("lead.id"), index=True)

    # NEW: actual recipient (needed for sending)
    to_email = Column(String, nullable=True, index=True)

    step_index = Column(Integer, default=0)

    # idempotency key (we generate: "{campaign_id}:{lead_id}:{step_index}")
    dedupe_key = Column(String, unique=True, index=True)

    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)

    status = Column(String, default="queued", index=True)  # queued | sent | failed
    provider = Column(String, default="m365")              # m365 | smtp | simulated

    provider_message_id = Column(String, nullable=True, index=True)
    thread_id = Column(String, nullable=True, index=True)

    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ----------------------------
# System Events (Operational logs)
# ----------------------------
class Event(Base):
    __tablename__ = "event"

    id = Column(Integer, primary_key=True, index=True)

    level = Column(String, default="INFO", index=True)  # INFO | WARN | ERROR
    event_type = Column(String, index=True)

    campaign_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)
    job_id = Column(Integer, nullable=True, index=True)

    message = Column(Text, nullable=True)
    data_json = Column(Text, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# ----------------------------
# Versioned strategy snapshots (recommended)
# ----------------------------
class CampaignStrategyVersion(Base):
    __tablename__ = "campaign_strategy_version"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaign.id"), index=True)

    version = Column(Integer, default=1)
    strategy_json = Column(Text, nullable=True)
    sequence_json = Column(Text, nullable=True)
    run_config_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# DB Helpers / Migrations
# ============================================================

def _set_sqlite_pragmas():
    """
    Desktop SQLite settings:
    - WAL mode for concurrency
    - busy_timeout to reduce "database is locked"
    """
    conn = engine.raw_connection()
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA busy_timeout=5000;")
    finally:
        conn.commit()
        conn.close()


def _ensure_campaign_columns():
    conn = engine.raw_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE campaign ADD COLUMN strategy_json TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE campaign ADD COLUMN sequence_json TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE campaign ADD COLUMN run_config_json TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def _ensure_job_queue_columns():
    """
    If your DB was created before campaign_id/lead_id were added to JobQueue,
    this adds them safely.
    """
    conn = engine.raw_connection()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE job_queue ADD COLUMN campaign_id INTEGER")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE job_queue ADD COLUMN lead_id INTEGER")
    except Exception:
        pass

    conn.commit()
    conn.close()


def _ensure_outbox_columns():
    """
    Ensure outbox has to_email and dedupe_key, etc.
    (SQLite cannot add UNIQUE constraints via ALTER TABLE; that's OK for MVP.)
    """
    conn = engine.raw_connection()
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE outbox_email ADD COLUMN to_email TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE outbox_email ADD COLUMN dedupe_key TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def init_db():
    _set_sqlite_pragmas()
    Base.metadata.create_all(bind=engine)

    # lightweight migrations
    _ensure_campaign_columns()
    _ensure_job_queue_columns()
    _ensure_outbox_columns()

    log_event("db.init", message="DB initialized; pragmas set; migrations checked")


def get_session():
    return SessionLocal()


# ============================================================
# Operational Event Logger
# ============================================================

def log_event(
    event_type: str,
    level: str = "INFO",
    campaign_id: int | None = None,
    lead_id: int | None = None,
    job_id: int | None = None,
    message: str | None = None,
    data: dict | None = None,
):
    session = get_session()
    row = Event(
        level=level,
        event_type=event_type,
        campaign_id=campaign_id,
        lead_id=lead_id,
        job_id=job_id,
        message=message,
        data_json=json.dumps(data) if data else None,
    )
    session.add(row)
    session.commit()
    session.close()
    return True


# ============================================================
# Workspace Save / Helpers
# ============================================================

def save_workspace(data):
    session = get_session()
    workspace = Workspace(
        company_name=data.company_name,
        offering=data.offering,
        icp=data.icp,
    )
    session.add(workspace)
    session.commit()
    session.close()


def get_latest_workspace():
    session = get_session()
    ws = session.query(Workspace).order_by(Workspace.id.desc()).first()
    session.close()
    return ws


# ============================================================
# Campaign helpers
# ============================================================

def create_campaign(workspace_id: int, name: str, cadence_days: int = 3, max_touches: int = 4):
    session = get_session()
    campaign = Campaign(
        workspace_id=workspace_id,
        name=name,
        status="draft",
        cadence_days=cadence_days,
        max_touches=max_touches,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    session.close()
    return campaign


def create_campaign_from_strategy(
    workspace_id: int,
    name: str,
    strategy: dict,
    sequence: dict,
    run_config: dict,
    status: str = "running",
    cadence_days: int = 3,
    max_touches: int = 4,
):
    """
    Creates a campaign fully from agent-generated strategy.
    Stores strategy_json + sequence_json + run_config_json.
    Also writes a version snapshot row.
    """
    session = get_session()

    campaign = Campaign(
        workspace_id=workspace_id,
        name=name,
        status=status,
        cadence_days=cadence_days,
        max_touches=max_touches,
        strategy_json=json.dumps(strategy),
        sequence_json=json.dumps(sequence),
        run_config_json=json.dumps(run_config),
    )

    session.add(campaign)
    session.commit()
    session.refresh(campaign)

    v = CampaignStrategyVersion(
        campaign_id=campaign.id,
        version=1,
        strategy_json=campaign.strategy_json,
        sequence_json=campaign.sequence_json,
        run_config_json=campaign.run_config_json,
    )
    session.add(v)
    session.commit()

    session.close()
    log_event("campaign.created", campaign_id=campaign.id, message=f"Campaign created: {campaign.name}")
    return campaign


def set_campaign_status(campaign_id: int, status: str):
    session = get_session()
    campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        session.close()
        return None
    campaign.status = status
    session.commit()
    session.refresh(campaign)
    session.close()
    log_event("campaign.status_changed", campaign_id=campaign_id, message=f"Status -> {status}")
    return campaign


def get_campaign(campaign_id: int):
    session = get_session()
    campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
    session.close()
    return campaign


def list_campaigns(workspace_id: int):
    session = get_session()
    campaigns = (
        session.query(Campaign)
        .filter(Campaign.workspace_id == workspace_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    session.close()
    return campaigns


def list_running_campaigns():
    session = get_session()
    rows = session.query(Campaign).filter(Campaign.status == "running").all()
    session.close()
    return rows


def save_campaign_sequence(campaign_id: int, sequence: dict):
    session = get_session()
    campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        session.close()
        return None
    campaign.sequence_json = json.dumps(sequence)
    session.commit()
    session.refresh(campaign)
    session.close()
    log_event("campaign.sequence_saved", campaign_id=campaign_id)
    return campaign


def save_campaign_strategy(campaign_id: int, strategy: dict):
    session = get_session()
    campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        session.close()
        return None
    campaign.strategy_json = json.dumps(strategy)
    session.commit()
    session.refresh(campaign)
    session.close()
    log_event("campaign.strategy_saved", campaign_id=campaign_id)
    return campaign


def save_campaign_run_config(campaign_id: int, run_config: dict):
    session = get_session()
    campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        session.close()
        return None
    campaign.run_config_json = json.dumps(run_config)
    session.commit()
    session.refresh(campaign)
    session.close()
    log_event("campaign.run_config_saved", campaign_id=campaign_id)
    return campaign


# ============================================================
# Lead helpers
# ============================================================

def add_leads_bulk(campaign_id: int, leads: list[dict]):
    """
    leads items: {"full_name": "...", "email": "...", "company": "..."}
    """
    session = get_session()

    existing = set(
        e[0] for e in session.query(Lead.email).filter(Lead.campaign_id == campaign_id).all()
        if e and e[0]
    )

    objs = []
    for l in leads:
        email = (l.get("email") or "").strip().lower()
        if not email or email in existing:
            continue
        existing.add(email)

        objs.append(
            Lead(
                campaign_id=campaign_id,
                full_name=(l.get("full_name") or "").strip(),
                email=email,
                company=(l.get("company") or "").strip(),
                state="NEW",
                touch_count=0,
                next_touch_at=datetime.utcnow(),
            )
        )

    session.add_all(objs)
    session.commit()
    count = len(objs)
    session.close()

    log_event("leads.uploaded", campaign_id=campaign_id, message=f"Inserted {count} leads")
    return count


def list_leads(campaign_id: int):
    session = get_session()
    leads = (
        session.query(Lead)
        .filter(Lead.campaign_id == campaign_id)
        .order_by(Lead.created_at.desc())
        .all()
    )
    session.close()
    return leads


def get_due_leads(campaign_id: int, limit: int = 10):
    session = get_session()
    now = datetime.utcnow()
    leads = (
        session.query(Lead)
        .filter(Lead.campaign_id == campaign_id)
        .filter(Lead.next_touch_at <= now)
        .filter(Lead.state.in_(["NEW", "FOLLOWUP"]))
        .order_by(Lead.next_touch_at.asc())
        .limit(limit)
        .all()
    )
    session.close()
    return leads


def mark_lead_waiting_reply(lead_id: int, cadence_days: int):
    session = get_session()
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        session.close()
        return None

    lead.touch_count = (lead.touch_count or 0) + 1
    lead.state = "WAITING_REPLY"
    lead.next_touch_at = datetime.utcnow() + timedelta(days=cadence_days)

    session.commit()
    session.refresh(lead)
    session.close()
    log_event("lead.waiting_reply", lead_id=lead_id)
    return lead


def schedule_followup(lead_id: int, days_from_now: int):
    session = get_session()
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        session.close()
        return None

    lead.state = "FOLLOWUP"
    lead.next_touch_at = datetime.utcnow() + timedelta(days=days_from_now)

    session.commit()
    session.refresh(lead)
    session.close()
    log_event("lead.followup_scheduled", lead_id=lead_id, data={"days": days_from_now})
    return lead


def stop_lead(lead_id: int, positive: bool, note: str = ""):
    session = get_session()
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        session.close()
        return None

    lead.state = "STOPPED_POSITIVE" if positive else "STOPPED_NEGATIVE"

    session.commit()
    session.refresh(lead)
    session.close()
    log_event("lead.stopped", lead_id=lead_id, level="INFO", message=note, data={"positive": positive})
    return lead


def complete_lead(lead_id: int, note: str = ""):
    session = get_session()
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        session.close()
        return None
    lead.state = "COMPLETED"
    session.commit()
    session.refresh(lead)
    session.close()
    log_event("lead.completed", lead_id=lead_id, message=note)
    return lead


# ============================================================
# Outbox helpers (Idempotent)
# ============================================================

def _dedupe_key(campaign_id: int, lead_id: int, step_index: int) -> str:
    return f"{campaign_id}:{lead_id}:{step_index}"


def get_outbox_email(lead_id: int, step_index: int, campaign_id: int | None = None):
    """
    Prefer dedupe_key lookup when campaign_id is provided.
    Fallback: lead_id + step_index.
    """
    session = get_session()

    row = None
    if campaign_id is not None:
        dk = _dedupe_key(campaign_id, lead_id, step_index)
        row = session.query(OutboxEmail).filter(OutboxEmail.dedupe_key == dk).first()

    if row is None:
        row = (
            session.query(OutboxEmail)
            .filter(OutboxEmail.lead_id == lead_id)
            .filter(OutboxEmail.step_index == step_index)
            .order_by(OutboxEmail.id.desc())
            .first()
        )

    session.close()
    return row


def create_outbox_email(
    lead_id: int,
    campaign_id: int,
    step_index: int,
    to_email: str,
    subject: str,
    body: str,
    provider: str = "m365",
):
    """
    Idempotent create:
    - If a row already exists for this (campaign, lead, step), return it.
    """
    existing = get_outbox_email(lead_id=lead_id, step_index=step_index, campaign_id=campaign_id)
    if existing:
        return existing

    session = get_session()
    row = OutboxEmail(
        campaign_id=campaign_id,
        lead_id=lead_id,
        to_email=to_email,
        step_index=step_index,
        dedupe_key=_dedupe_key(campaign_id, lead_id, step_index),
        subject=subject,
        body=body,
        status="queued",
        provider=provider,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    session.close()

    log_event(
        "outbox.created",
        campaign_id=campaign_id,
        lead_id=lead_id,
        message=f"outbox_id={row.id} step_index={step_index}",
    )
    return row


def mark_outbox_sent(outbox_id: int, provider_message_id: str | None = None):
    session = get_session()
    row = session.query(OutboxEmail).filter(OutboxEmail.id == outbox_id).first()
    if not row:
        session.close()
        return None

    row.status = "sent"
    row.provider_message_id = provider_message_id
    row.sent_at = datetime.utcnow()

    session.commit()
    session.refresh(row)
    session.close()

    log_event("outbox.sent", campaign_id=row.campaign_id, lead_id=row.lead_id, message=f"outbox_id={outbox_id}")
    return row


def mark_outbox_failed(outbox_id: int, err: str):
    session = get_session()
    row = session.query(OutboxEmail).filter(OutboxEmail.id == outbox_id).first()
    if not row:
        session.close()
        return None

    row.status = "failed"
    row.last_error = err

    session.commit()
    session.refresh(row)
    session.close()

    log_event(
        "outbox.failed",
        level="ERROR",
        campaign_id=row.campaign_id,
        lead_id=row.lead_id,
        message=f"outbox_id={outbox_id}",
        data={"error": err},
    )
    return row


# ============================================================
# Activity helpers (Human-friendly)
# ============================================================

def log_activity(lead_id: int, type: str, message: str):
    session = get_session()
    row = ActivityLog(lead_id=lead_id, type=type, message=message)
    session.add(row)
    session.commit()
    session.refresh(row)
    session.close()
    return row


def get_campaign_activity(campaign_id: int, limit: int = 200):
    session = get_session()
    rows = (
        session.query(ActivityLog)
        .join(Lead, ActivityLog.lead_id == Lead.id)
        .filter(Lead.campaign_id == campaign_id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    session.close()
    return rows
