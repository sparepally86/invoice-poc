# app/api/feedback.py
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Body, Path, HTTPException
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db

router = APIRouter()

# small helper to run sync DB calls in a thread
def _to_thread(fn, *a, **kw):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*a, **kw))


@router.post("/api/v1/feedback", response_class=JSONResponse)
async def post_feedback(payload: Dict[str, Any] = Body(...)):
    """
    Store reviewer feedback.

    Body:
    {
      "invoice_id": "INV-123",
      "step_id": "step-abc",    # optional: the explain step id or timestamp
      "verdict": "accept|reject|suggest_edit",
      "notes": "free text optional",
      "user": "ui:user-id"
    }
    """
    db = get_db()
    invoice_id = payload.get("invoice_id")
    verdict = payload.get("verdict")
    notes = payload.get("notes", "")
    step_id = payload.get("step_id")
    user = payload.get("user", "ui:anonymous")

    if not invoice_id or not verdict:
        raise HTTPException(status_code=400, detail="invoice_id and verdict are required")

    doc = {
        "invoice_id": invoice_id,
        "step_id": step_id,
        "verdict": verdict,
        "notes": notes,
        "user": user,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    try:
        res = await _to_thread(db.feedback.insert_one, doc)
        return JSONResponse({"ok": True, "inserted_id": str(getattr(res, "inserted_id", None) or res)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_insert_failed: {str(e)}")


@router.get("/api/v1/invoices/{invoice_id}/feedback", response_class=JSONResponse)
async def get_feedback(invoice_id: str = Path(...)):
    """
    Return recent feedback entries for the invoice (most recent first).
    """
    db = get_db()
    try:
        # fetch recent 50 feedback docs for this invoice
        cursor = await _to_thread(db.feedback.find, {"invoice_id": invoice_id})
        # convert to list in thread to avoid iterating the cursor in event loop
        docs = await _to_thread(list, cursor.sort("created_at", -1).limit(50))
        # sanitize ObjectId if present
        results = []
        for d in docs:
            d2 = {k: (str(v) if k == "_id" else v) for k, v in d.items()}
            results.append(d2)
        return JSONResponse({"ok": True, "invoice_id": invoice_id, "feedback": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_read_failed: {str(e)}")
