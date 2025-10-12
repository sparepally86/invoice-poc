# app/api/explain.py
from fastapi import APIRouter, Body, Path, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from app.storage.mongo_client import get_db
from app.agents.explain import run_explain

router = APIRouter()

@router.post("/invoices/{invoice_id}/explain", response_class=JSONResponse)
async def post_explain(invoice_id: str = Path(...), payload: dict = Body({})):
    """Debug-friendly POST that logs full traceback on failures and returns it in response."""
    import traceback
    from datetime import datetime

    db = get_db()
    try:
        inv = await asyncio_to_thread(db.invoices.find_one, {"_id": invoice_id})
        if not inv:
            return JSONResponse({"ok": False, "error": "invoice_not_found"}, status_code=404)

        # Run explain in thread and capture any exception
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: run_explain(db, inv, (payload or {}).get("triggering_step", {})))
        except Exception:
            tb = traceback.format_exc()
            print("run_explain raised an exception:\n", tb, flush=True)
            return JSONResponse({"ok": False, "error": "run_explain_failed", "traceback": tb}, status_code=500)

        # Persist the step into invoice._workflow.steps
        try:
            step_obj = resp
            if not inv.get("_workflow"):
                inv["_workflow"] = {"steps": []}
            if not isinstance(inv["_workflow"].get("steps"), list):
                inv["_workflow"]["steps"] = list(inv["_workflow"].get("steps") or [])
            # ensure timestamp exists
            if "timestamp" not in step_obj:
                step_obj["timestamp"] = datetime.utcnow().isoformat() + "Z"
            inv["_workflow"]["steps"].append(step_obj)
            await asyncio_to_thread(db.invoices.replace_one, {"_id": invoice_id}, inv)
        except Exception:
            tb = traceback.format_exc()
            print("persist explain step failed:\n", tb, flush=True)
            return JSONResponse({"ok": True, "explain": resp, "warn": "persist_failed", "persist_traceback": tb})

        return JSONResponse({"ok": True, "explain": resp})
    except Exception:
        tb = traceback.format_exc()
        print("post_explain top-level error:\n", tb, flush=True)
        return JSONResponse({"ok": False, "error": "server_error", "traceback": tb}, status_code=500)


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
