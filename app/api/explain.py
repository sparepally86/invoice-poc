# app/api/explain.py
from fastapi import APIRouter, Body, Path, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from app.storage.mongo_client import get_db
from app.agents.explain import run_explain

router = APIRouter()

@router.post("/invoices/{invoice_id}/explain", response_class=JSONResponse)
async def explain_invoice(
    invoice_id: str = Path(..., description="Invoice _id to explain"),
    payload: Optional[Dict[str, Any]] = Body(None),
):
    """
    Trigger ExplainAgent for the given invoice.
    Body (optional):
      { "triggering_step": {...} }  # an agent step that triggered this explain call
    If triggering_step is omitted, ExplainAgent will be called with an empty triggering step.
    The ExplainAgent response is persisted into invoice._workflow.steps[] and returned.
    """
    db = get_db()
    invoice = await asyncio_to_thread(db.invoices.find_one, {"_id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    triggering_step = (payload or {}).get("triggering_step", {}) if payload else {}
    try:
        # run_explain is synchronous; run in thread so we don't block event loop
        explain_resp = await asyncio_to_thread(run_explain, db, invoice, triggering_step)
        # persist the explain step into invoice workflow
        # ensure timestamp exists
        if "timestamp" not in explain_resp:
            from datetime import datetime
            explain_resp["timestamp"] = datetime.utcnow().isoformat() + "Z"
        await asyncio_to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": explain_resp}})
        return JSONResponse({"ok": True, "explain": explain_resp})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"explain_failed: {str(e)}")


@router.get("/invoices/{invoice_id}/explain", response_class=JSONResponse)
async def get_latest_explain(invoice_id: str = Path(..., description="Invoice _id to fetch explanation for")):
    """
    Return the most recent ExplainAgent step for the specified invoice.
    """
    db = get_db()
    invoice = await asyncio_to_thread(db.invoices.find_one, {"_id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    # Invoice may store workflow steps in _workflow.steps or similar; try to find steps list
    steps = invoice.get("_workflow", {}).get("steps") or invoice.get("workflow", {}).get("steps") or []
    # filter explain steps
    explain_steps = [s for s in steps if s.get("agent") == "ExplainAgent"]
    if not explain_steps:
        return JSONResponse({"ok": True, "explain": None, "message": "no_explain_found"})
    # return the latest by timestamp (or last)
    try:
        latest = sorted(explain_steps, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
    except Exception:
        latest = explain_steps[-1]
    return JSONResponse({"ok": True, "explain": latest})


# ---- helper: run sync functions in thread ----
import asyncio
from typing import Callable, Any
def asyncio_to_thread(fn: Callable, *a, **kw) -> Any:
    """
    Simple wrapper to run a blocking function in a thread and await its result.
    Provided to avoid adding additional dependencies.
    """
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*a, **kw))
