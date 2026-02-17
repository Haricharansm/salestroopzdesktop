# app/db/sqlite.py

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import event

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import time
from sqlalchemy.exc import OperationalError


# =============================================================================
# DB Location (IMPORTANT)
# -----------------------------------------------------------------------------
# Force the DB file to live in the agent/ folder (stable path),
# instead of "whatever directory you launched python from".
# =============================================================================

# sqlite.py is at: agent/app/db/sqlite.py
AGENT_DIR = Path(__file__).resolve().parents[2]  # -> agent/
DEFAULT_DB_FILE = AGENT_DIR / "salestroopz.db"

# Allow override from env
DB_FILE = Path(os.getenv("SQLITE_DB_FILE", str(DEFAULT_DB_FILE)))
if not DB_FILE.is_absolute():
    DB_FILE = (AGENT_DIR / DB_FILE).resolve()

DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)
@event.listens_for(engine, "connect")
def _sqlite_on_connect(dbapi_conn, conn_record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()




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


# =============================================================================
# Runtime Tables
# =============================================================================

# ----------------------------
# Durable Job Queue (SQLite-backed)
# ----------------------------
class JobQueue(Base):
    __tablename__ = "job_queue"

    id = Column(Integer, primary_key=True, index=True)

    # Optional denormalized pointers (helps debugging + filtering)
    campaign_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)

    job_type = Column(String, index=True)                  # tick | generate_copy | send_email | poll_replies | decide_next
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


# ----------------------------
# Outbox (Idempotent sending)
# ----------------------------
class OutboxEmail(Base):
    __tablename__ = "outbox_email"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaign.id"), index=True)
    lead_id = Column(Integer, ForeignKey("lead.id"), index=True)

    step_index = Column(Integer, default=0)
    dedupe_key = Column(String, unique=True, index=True)

    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)

    status = Column(String, default="queued", index=True)  # queued | sent | failed
    provider = Column(String, default="m365")

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
# Versioned strategy snapshots
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

class InboxMessage(Base):
    __tablename__ = "inbox_message"
    id = Column(Integer, primary_key=True)
    provider = Column(String, default="m365", index=True)

    campaign_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)

    # Correlation keys
    from_email = Column(String, index=True)
    subject = Column(String, nullable=True)
    provider_message_id = Column(String, unique=True, index=True)
    thread_id = Column(String, nullable=True, index=True)

    received_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Raw + normalized
    body_preview = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)

    processed = Column(Integer, default=0, index=True)  # 0/1

class LeadDecision(Base):
    __tablename__ = "lead_decision"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.id"), index=True)
    campaign_id = Column(Integer, nullable=True, index=True)

    decision = Column(String, index=True)  # POSITIVE | NEGATIVE | NEUTRAL | OOO | UNSUB | MEETING
    confidence = Column(Integer, default=0) # 0-100
    rationale = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# =============================================================================
# DB Helpers / Migrations
# =============================================================================

def _set_sqlite_pragmas():
    """
    Recommended for production-ish SQLite on a desktop app:
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
    Your DB already shows these columns exist in job_queue in screenshots.
    But for anyone on an older DB, add them safely.
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


def init_db():
    _set_sqlite_pragmas()
    Base.metadata.create_all(bind=engine)
    _ensure_campaign_columns()
    _ensure_job_queue_columns()


def get_session():
    return SessionLocal()


# =============================================================================
# Operational Event Logger
# =============================================================================


def log_event(
    event_type: str,
    level: str = "INFO",
    campaign_id: int | None = None,
    lead_id: int | None = None,
    job_id: int | None = None,
    message: str | None = None,
    data: dict | None = None,
):
    for i in range(6):
        session = get_session()
        try:
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
            return True
        except OperationalError as e:
            session.rollback()
            if "database is locked" not in str(e).lower():
                raise
            time.sleep(0.2 * (i + 1))  # backoff
        finally:
            session.close()

    # If still locked after retries, don't crash the app.
    return False



# =============================================================================
# Workspace helpers
# =============================================================================

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


# =============================================================================
# Campaign helpers
# =============================================================================

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


# =============================================================================
# Lead helpers
# =============================================================================

def add_leads_bulk(campaign_id: int, leads: list[dict]):
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


# =============================================================================
# Activity helpers
# =============================================================================

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
