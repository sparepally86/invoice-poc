# app/api/dev_explain.py
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any
from app.agents.explain import run_explain
from app.storage.mongo_client import get_db

router = APIRouter()

@router.post("/api/v1/dev/explain", response_class=JSONResponse)
async def dev_explain(payload: Dict[str, Any] = Body(...)):
    """
    Dev endpoint to trigger ExplainAgent.
    Body:
    {
      "invoice": { ... invoice JSON ... },
      "triggering_step": { ... agent step ... }
    }
    """
    db = get_db()
    invoice = payload.get("invoice") or {}
    triggering_step = payload.get("triggering_step") or {}
    resp = run_explain(db, invoice, triggering_step)
    return JSONResponse({"ok": True, "explain": resp})
