from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import csv
import io

from app.db.sqlite import (
    get_latest_workspace,
    create_campaign,
    set_campaign_status,
    list_leads,
    list_leads_page,  # ✅ NEW (paginated)
    add_leads_bulk,
    get_campaign_activity,
    get_campaign,
    save_campaign_sequence,
)

router = APIRouter(prefix="/campaign", tags=["campaign"])


class CampaignCreateRequest(BaseModel):
    workspace_id: int | None = None
    name: str
    cadence_days: int = 3
    max_touches: int = 4


@router.post("")
def create(req: CampaignCreateRequest):
    ws_id = req.workspace_id
    if ws_id is None:
        ws = get_latest_workspace()
        if not ws:
            raise HTTPException(status_code=400, detail="No workspace found. Create workspace first.")
        ws_id = ws.id

    c = create_campaign(ws_id, req.name, req.cadence_days, req.max_touches)
    return {"campaign_id": c.id, "status": c.status}


@router.post("/{campaign_id}/start")
def start(campaign_id: int):
    c = set_campaign_status(campaign_id, "running")
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign_id": c.id, "status": c.status}


@router.post("/{campaign_id}/pause")
def pause(campaign_id: int):
    c = set_campaign_status(campaign_id, "paused")
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign_id": c.id, "status": c.status}

@router.get("/{campaign_id}")
def get_campaign_status(campaign_id: int):
    c = get_campaign(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {
        "campaign_id": c.id,
        "workspace_id": c.workspace_id,
        "name": c.name,
        "status": c.status,
        "cadence_days": c.cadence_days,
        "max_touches": c.max_touches,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }

@router.get("/{campaign_id}/leads")
def leads(campaign_id: int, limit: int | None = None, offset: int | None = None):
    """
    Production-ready leads API.

    Back-compat:
      - If limit/offset are NOT provided, return the original LIST response.
    New behavior:
      - If limit/offset are provided, return:
          { items: [...], total: N, limit, offset }
    """
    # ✅ Paginated response
    if limit is not None or offset is not None:
        lim = int(limit or 50)
        off = int(offset or 0)

        rows, total = list_leads_page(campaign_id, limit=lim, offset=off)
        items = [
            {
                "id": l.id,
                "full_name": l.full_name,
                "email": l.email,
                "company": l.company,
                "state": l.state,
                "touch_count": l.touch_count,
                "next_touch_at": l.next_touch_at.isoformat() if l.next_touch_at else None,
            }
            for l in rows
        ]
        return {"items": items, "total": total, "limit": lim, "offset": off}

    # ✅ Original response (list)
    rows = list_leads(campaign_id)
    return [
        {
            "id": l.id,
            "full_name": l.full_name,
            "email": l.email,
            "company": l.company,
            "state": l.state,
            "touch_count": l.touch_count,
            "next_touch_at": l.next_touch_at.isoformat() if l.next_touch_at else None,
        }
        for l in rows
    ]


@router.get("/{campaign_id}/activity")
def activity(campaign_id: int, limit: int = 200):
    rows = get_campaign_activity(campaign_id, limit=limit)
    return [
        {
            "id": a.id,
            "lead_id": a.lead_id,
            "type": a.type,
            "message": a.message,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in rows
    ]


@router.post("/{campaign_id}/leads/upload")
async def upload_leads(campaign_id: int, file: UploadFile = File(...)):
    c = get_campaign(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    leads = []
    for row in reader:
        leads.append(
            {
                "full_name": row.get("full_name") or row.get("name") or "",
                "email": row.get("email") or "",
                "company": row.get("company") or "",
            }
        )

    inserted = add_leads_bulk(campaign_id, leads)
    return {"inserted": inserted}


class SequenceSaveRequest(BaseModel):
    name: str
    steps: list[dict]
    stop_rule: str = "stop_on_negative"


@router.post("/{campaign_id}/sequence")
def save_sequence(campaign_id: int, req: SequenceSaveRequest):
    c = save_campaign_sequence(campaign_id, req.model_dump())
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign_id": c.id, "saved": True}



