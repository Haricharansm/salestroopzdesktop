import os
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.llm.ollama_client import check_ollama, generate_text
from app.db.sqlite import init_db, save_workspace, log_event
from app.schemas.models import WorkspaceRequest

from app.m365.auth import M365Auth, SCOPES as M365_SCOPES
from app.m365.client import M365Client

from app.api.campaign_routes import router as campaign_router
from app.api.agent_routes import router as agent_router


app = FastAPI(title="Salestroopz Local Agent")

# CORS for Vite/React -> FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local desktop; tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers AFTER app is created
app.include_router(campaign_router)
app.include_router(agent_router)

# --- M365 setup ---
# NOTE: keep this lightweight; device-flow does the real work later
try:
    m365_auth = M365Auth()
except Exception:
    m365_auth = None

_device_flow_holder = {"flow": None}


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str


# ----------------------------
# Startup: init DB + bootstrap autonomous tick
# ----------------------------
@app.on_event("startup")
def on_startup():
    """
    Keep startup safe + fast:
    - init DB
    - enqueue first scheduler tick (fails soft if queue not present yet)
    """
    init_db()
    try:
        # Only available after you add app/queue/job_queue.py
        from app.queue.job_queue import enqueue

        # Seed the scheduler loop (runner will keep scheduling subsequent ticks)
        enqueue("tick", {}, run_at=datetime.utcnow() + timedelta(seconds=1))
        log_event("api.startup", message="DB initialized; tick seeded")
    except Exception as e:
        # Do not crash API if queue isn't wired yet
        try:
            log_event("api.startup.no_queue", level="WARN", message=str(e))
        except Exception:
            pass


# ----------------------------
# Health & Status
# ----------------------------
@app.get("/health")
def health():
    """
    Electron waits on this endpoint to decide backend readiness.
    Keep it fast and deterministic.
    """
    return {
        "ok": True,
        "service": "salestroopz-api",
        "status": "running",
    }


@app.get("/ollama/status")
def ollama_status():
    return {"ollama_running": check_ollama()}


# ----------------------------
# Workspace + Simple LLM test
# ----------------------------
@app.post("/workspace")
def create_workspace(data: WorkspaceRequest):
    save_workspace(data)
    return {"message": "Workspace saved locally"}


@app.post("/campaign/generate")
def generate_campaign(prompt: str):
    result = generate_text(prompt)
    return {"campaign_text": result}


# -------------------
# M365 endpoints
# -------------------
def _m365_config_snapshot():
    """
    Returns config + cache diagnostics without requiring auth to succeed.
    Matches your current M365Auth env keys:
      - M365_CLIENT_ID
      - M365_TENANT_ID
      - TOKEN_CACHE_PATH
    """
    client_id = os.getenv("M365_CLIENT_ID", "")
    tenant_id = os.getenv("M365_TENANT_ID", "common")
    cache_path = os.getenv("TOKEN_CACHE_PATH", "./data/token_cache.json")

    cache_exists = False
    cache_size = 0
    try:
        p = Path(cache_path)
        cache_exists = p.exists()
        cache_size = p.stat().st_size if cache_exists else 0
    except Exception:
        pass

    return {
        "client_id_present": bool(client_id),
        "tenant_id": tenant_id,
        "authority": f"https://login.microsoftonline.com/{tenant_id}",
        "token_cache_path": cache_path,
        "token_cache_exists": cache_exists,
        "token_cache_size": cache_size,
        "scopes": list(M365_SCOPES),
    }


@app.get("/m365/scopes")
def m365_scopes():
    """
    Debug endpoint: tells UI what the backend is configured to request.
    Useful when diagnosing consent issues.
    """
    return _m365_config_snapshot()


@app.get("/m365/status")
def m365_status():
    """
    Reliable connection state for UI:
      - configured flags even when not connected
      - connected flag only if silent token works
      - user identity (displayName/mail) when connected
    """
    snapshot = _m365_config_snapshot()

    if not m365_auth:
        return {
            **snapshot,
            "configured": False,
            "connected": False,
            "has_cached_account": False,
            "error": "M365Auth not initialized. Set M365_CLIENT_ID and restart backend.",
        }

    # Try silent token (no UI). This is the canonical "connected" signal.
    try:
        token = m365_auth.acquire_token_silent()
    except Exception as e:
        return {
            **snapshot,
            "configured": True,
            "connected": False,
            "has_cached_account": False,
            "error": f"Silent token failed: {str(e)}",
        }

    access_token = token.get("access_token") if isinstance(token, dict) else None
    if not access_token:
        # Determine if at least one account is cached
        try:
            has_account = bool(m365_auth.app.get_accounts())
        except Exception:
            has_account = False

        return {
            **snapshot,
            "configured": True,
            "connected": False,
            "has_cached_account": has_account,
        }

    # If we have an access token, fetch profile as final confirmation
    try:
        client = M365Client(access_token)
        me = client.me()
        return {
            **snapshot,
            "configured": True,
            "connected": True,
            "has_cached_account": True,
            "user": {
                "displayName": me.get("displayName"),
                "mail": me.get("mail") or me.get("userPrincipalName"),
            },
        }
    except Exception as e:
        # Token exists but profile fetch failed (rare) — still show connected=false to be safe
        return {
            **snapshot,
            "configured": True,
            "connected": False,
            "has_cached_account": True,
            "error": f"Token acquired but /me failed: {str(e)}",
        }


@app.post("/m365/device/start")
def m365_device_start():
    if not m365_auth:
        raise HTTPException(status_code=500, detail="M365 not configured. Set M365_CLIENT_ID.")

    flow = m365_auth.start_device_flow()
    _device_flow_holder["flow"] = flow
    return {
        "user_code": flow["user_code"],
        "verification_uri": flow["verification_uri"],
        "message": flow["message"],
    }


@app.post("/m365/device/complete")
def m365_device_complete():
    if not m365_auth:
        raise HTTPException(status_code=500, detail="M365 not configured. Set M365_CLIENT_ID.")

    flow = _device_flow_holder.get("flow")
    if not flow:
        raise HTTPException(status_code=400, detail="No device flow started")

    token = m365_auth.complete_device_flow(flow)
    if "access_token" not in token:
        raise HTTPException(status_code=401, detail=str(token))

    _device_flow_holder["flow"] = None
    return {"connected": True}


@app.post("/m365/send")
def m365_send(req: SendEmailRequest):
    if not m365_auth:
        raise HTTPException(status_code=500, detail="M365 not configured. Set M365_CLIENT_ID.")

    token = m365_auth.acquire_token_silent()
    if not token or "access_token" not in token:
        raise HTTPException(status_code=401, detail="Not connected to Microsoft 365")

    client = M365Client(token["access_token"])
    client.send_mail(req.to_email, req.subject, req.body)
    return {"sent": True}
