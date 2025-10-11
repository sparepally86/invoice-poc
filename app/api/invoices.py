# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from bson import ObjectId
from starlette.responses import StreamingResponse
import json
import asyncio

router = APIRouter()

# helper synchronous wrappers for PyMongo calls (run via asyncio.to_thread)
def _find_one_sync(coll, q):
    return coll.find_one(q)

def _count_sync(coll, q=None):
    if q is None:
        q = {}
    return coll.count_documents(q)

# SSE helper
def format_sse(event: str, data: dict):
    payload = f"event: {event}\n"
    payload += f"data: {json.dumps(data, default=str)}\n\n"
    return payload


def ensure_minimal_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize payload to be tolerant and backward-compatible.
    Ensures:
      - payload['lines'] and payload['items'] both exist and mirror each other.
      - header.amount is populated (float) from common shapes like header.grand_total.value
      - header.grand_total exists and contains numeric 'value' where possible
      - each invoice line has a numeric 'amount' field (float) derived from common keys)
    """
    payload = dict(payload) if payload else {}
    # Header normalization (support multiple shapes)
    header = payload.get('header') or {}
    if not isinstance(header, dict):
        header = {}

    # invoice_ref can be present as header.invoice_ref (string) or header.invoice_number dict
    inv_ref = header.get('invoice_ref') or None
    inv_number = header.get('invoice_number')
    if isinstance(inv_number, dict):
        inv_ref = inv_number.get('value') or inv_ref
    if inv_ref and not header.get('invoice_ref'):
        header['invoice_ref'] = inv_ref

    # Ensure lines/items exist and mirror
    _lines = payload.get('lines') if payload.get('lines') is not None else payload.get('items', [])
    if _lines is None:
        _lines = []
    if not isinstance(_lines, list):
        _lines = [_lines]
    payload['lines'] = _lines
    payload['items'] = list(_lines)

    # Normalize header.amount (float) from grand_total or other common keys if missing
    if 'amount' not in header or header.get('amount') in (None, ''):
        gt = header.get('grand_total')
        if isinstance(gt, dict) and 'value' in gt:
            try:
                header['amount'] = float(gt.get('value') or 0.0)
            except Exception:
                pass
        elif isinstance(gt, (int, float, str)) and gt != "":
            try:
                header['amount'] = float(gt)
            except Exception:
                pass
        else:
            for k in ('total', 'grand_total_amount', 'amount_total'):
                if k in header:
                    try:
                        header['amount'] = float(header.get(k))
                        break
                    except Exception:
                        pass

    # Ensure header.grand_total is a dict with numeric 'value'
    if not isinstance(header.get('grand_total'), dict):
        if 'amount' in header:
            try:
                header['grand_total'] = {'value': float(header['amount'])}
            except Exception:
                header['grand_total'] = {'value': header.get('amount')}
    else:
        try:
            header['grand_total']['value'] = float(header['grand_total'].get('value') or header.get('amount') or 0.0)
        except Exception:
            pass

    # Normalize per-line amounts to ensure 'amount' exists and is float
    for ln in payload.get('lines', []):
        if not isinstance(ln, dict):
            continue
        if 'amount' in ln and ln.get('amount') not in (None, ''):
            try:
                ln['amount'] = float(ln.get('amount'))
            except Exception:
                try:
                    ln['amount'] = float(str(ln.get('amount')).replace(',', '').strip())
                except Exception:
                    ln['amount'] = 0.0
        else:
            found = False
            for key in ('line_total', 'total', 'price', 'value', 'amount_total'):
                if key in ln and ln.get(key) not in (None, ''):
                    try:
                        ln['amount'] = float(ln.get(key))
                        found = True
                        break
                    except Exception:
                        try:
                            ln['amount'] = float(str(ln.get(key)).replace(',', '').strip())
                            found = True
                            break
                        except Exception:
                            pass
            if not found:
                ln['amount'] = 0.0

    payload['header'] = header
    return payload
    payload.setdefault("validation", {})
    payload.setdefault("ml_metadata", {})

    return payload


@router.post("/incoming", response_class=JSONResponse)
async def incoming_invoice(payload: dict = Body(...)):
    """
    Accept canonical invoice JSON, store it in invoices collection (with deterministic _id),
    and enqueue a processing task in tasks collection.
    """
    db = get_db()

    # Normalize payload minimally and pick invoice id
    payload = ensure_minimal_structure(payload)
    header = payload.get("header", {}) or {}

    # Pick invoice_ref: header.invoice_ref (str) or header.invoice_number.value
    invoice_ref = header.get("invoice_ref")
    if not invoice_ref:
        inv_num = header.get("invoice_number")
        if isinstance(inv_num, dict):
            invoice_ref = inv_num.get("value")
        else:
            invoice_ref = inv_num

    if not invoice_ref:
        invoice_ref = f"INV-{uuid.uuid4().hex[:8]}"

    invoice_id = invoice_ref

    now = datetime.utcnow().isoformat() + "Z"

    invoice_doc = {
        **payload,
        "_id": invoice_id,
        "status": "RECEIVED",
        "_workflow": {"steps": []},
        "created_at": now
    }

    # store invoice (upsert to be idempotent in POC)
    try:
        db.invoices.replace_one({"_id": invoice_id}, invoice_doc, upsert=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store invoice: {e}")

    # enqueue processing task
    task_doc = {
        "type": "process_invoice",
        "invoice_id": invoice_id,
        "status": "queued",
        "created_at": now
    }
    try:
        db.tasks.insert_one(task_doc)
    except Exception as e:
        # invoice stored but task creation failed
        return JSONResponse({"invoice_id": invoice_id, "status": "stored_task_failed", "error": str(e)}, status_code=500)

    return JSONResponse({"invoice_id": invoice_id, "status": "queued"})


@router.get("/invoices/{invoice_id}", response_class=JSONResponse)
async def get_invoice(invoice_id: str):
    """
    Robust invoice fetch:
    1) try _id
    2) fallback to header.invoice_ref
    3) fallback to header.invoice_number.value (common Capture shape)
    Returns full invoice doc (including _workflow.steps).
    """
    db = get_db()

    # 1) try by _id
    rec = db.invoices.find_one({"_id": invoice_id})
    if rec:
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    # 2) fallback: header.invoice_ref
    rec = db.invoices.find_one({"header.invoice_ref": invoice_id})
    if rec:
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    # 3) fallback: header.invoice_number.value
    rec = db.invoices.find_one({"header.invoice_number.value": invoice_id})
    if rec:
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    raise HTTPException(status_code=404, detail=f"invoice not found for id/ref: {invoice_id}")


@router.get("/invoices", response_class=JSONResponse)
async def list_invoices(limit: int = Query(50, ge=1, le=1000), q: Optional[str] = Query(None)):
    """
    Simple list endpoint for invoices.
    - ?limit=50  (max 1000)
    - ?q=TERM    (matches _id, header.invoice_ref, header.po_number, header.po)
    Returns: { "items": [ {..invoice..}, ... ] }
    """
    db = get_db()
    # build filter
    flt = {}
    if q:
        # basic exact or header matches
        flt = {
            "$or": [
                {"_id": q},
                {"header.invoice_ref": q},
                {"header.po_number": q},
                {"header.po": q},
            ]
        }

    try:
        # find and sort newest first
        cursor = db.invoices.find(flt).sort("created_at", -1).limit(int(limit))
        docs = []
        for d in cursor:
            # Convert ObjectId to string if present
            if isinstance(d.get("_id"), ObjectId):
                d["_id"] = str(d["_id"])
            # sanitize other non-serializable fields if needed (datetimes usually are iso strings already)
            # Keep only lightweight view to speed up UI
            item = {
                "_id": d.get("_id"),
                "header": d.get("header", {}),
                "status": d.get("status"),
                "_workflow": {"steps": d.get("_workflow", {}).get("steps", [])[-3:]},  # keep last 3 steps
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
            docs.append(item)
        return JSONResponse({"items": docs})
    except Exception as e:
        return JSONResponse({"error": "list_failed", "detail": str(e)}, status_code=500)

# endpoint
@router.get("/invoices/{invoice_id}/events", response_class=JSONResponse)
async def invoice_events(request: Request, invoice_id: str):
    """
    SSE streaming endpoint for invoice workflow updates.
    NOTE: uses asyncio.to_thread(...) to call blocking PyMongo safely.
    """

    db = get_db()

    async def event_generator():
        # initial fetch (blocking via to_thread)
        try:
            inv = await asyncio.to_thread(_find_one_sync, db.invoices, {"_id": invoice_id})
        except Exception as e:
            # DB error — send an error event then stop
            yield format_sse("error", {"message": "DB error", "detail": str(e)})
            return

        last_steps_len = 0
        if inv:
            wf = inv.get("_workflow", {}) or {}
            steps = wf.get("steps", []) or []
            last_steps_len = len(steps)
            # send initial snapshot to client
            yield format_sse("init", {"invoice_id": invoice_id, "workflow": wf, "created_at": inv.get("created_at")})
        else:
            # invoice not found initially; tell client and continue waiting (or break)
            yield format_sse("not_found", {"invoice_id": invoice_id})
            # still continue — maybe invoice will be created soon

        # Poll loop: check for new steps periodically
        try:
            while True:
                # Stop streaming if client disconnected
                if await request.is_disconnected():
                    break

                # fetch current invoice doc
                inv = await asyncio.to_thread(_find_one_sync, db.invoices, {"_id": invoice_id})
                if not inv:
                    # invoice deleted or not yet created
                    # send a not_found event and continue polling (or break if you prefer)
                    yield format_sse("not_found", {"invoice_id": invoice_id})
                    await asyncio.sleep(1.0)
                    continue

                wf = inv.get("_workflow", {}) or {}
                steps = wf.get("steps", []) or []
                if len(steps) > last_steps_len:
                    new_steps = steps[last_steps_len:]
                    for s in new_steps:
                        # send individual step events
                        yield format_sse("step", {"invoice_id": invoice_id, "step": s})
                    last_steps_len = len(steps)

                # Optionally also report status heartbeat if you want
                await asyncio.sleep(0.8)  # poll frequency (adjust as needed)
        except asyncio.CancelledError:
            # client disconnected or server shutting down
            return
        except Exception as e:
            # unexpected error - notify client then exit
            yield format_sse("error", {"message": "stream error", "detail": str(e)})
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ------------------------------
# Helper for status + workflow updates
# ------------------------------
def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _append_workflow_step_and_update_status(db, invoice_id: str, step: Dict[str, Any], new_status: Optional[str] = None):
    """
    Append a workflow step and optionally set status/updated_at.
    This uses blocking pymongo client calls and is intended to be called directly (synchronously).
    """
    update_doc = {"$push": {"_workflow.steps": step}}
    if new_status:
        update_doc["$set"] = {"status": new_status, "updated_at": _now_iso()}
    db.invoices.update_one({"_id": invoice_id}, update_doc)


# ------------------------------
# Approve / Reject endpoints
# ------------------------------
@router.post("/invoices/{invoice_id}/approve", response_class=JSONResponse)
async def approve_invoice(invoice_id: str, payload: Dict[str, Any] = Body(None)):
    """
    Approve invoice via UI.

    Body (optional):
    {
      "approver": "user:alice",
      "comment": "Looks good"
    }

    Result: sets status -> READY_FOR_POSTING and appends workflow step.
    """
    body = payload or {}
    approver = body.get("approver", "ui:unknown")
    comment = body.get("comment", "")

    db = get_db()

    # fetch invoice
    rec = db.invoices.find_one({"_id": invoice_id})
    if not rec:
        # try fallback lookups (as in get_invoice)
        rec = db.invoices.find_one({"header.invoice_ref": invoice_id}) or db.invoices.find_one({"header.invoice_number.value": invoice_id})
        if not rec:
            raise HTTPException(status_code=404, detail="invoice_not_found")
        invoice_id = rec.get("_id")

    # workflow step
    step = {
        "agent": "HumanApprovalUI",
        "type": "approve",
        "invoice_id": invoice_id,
        "actor": approver,
        "result": {"action": "approve", "comment": comment},
        "timestamp": _now_iso()
    }

    try:
        _append_workflow_step_and_update_status(db, invoice_id, step, new_status="READY_FOR_POSTING")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"approve_failed: {e}")

    updated = db.invoices.find_one({"_id": invoice_id})
    if isinstance(updated.get("_id"), ObjectId):
        updated["_id"] = str(updated["_id"])
    return JSONResponse({"ok": True, "invoice": updated})


@router.post("/invoices/{invoice_id}/reject", response_class=JSONResponse)
async def reject_invoice(invoice_id: str, payload: Dict[str, Any] = Body(None)):
    """
    Reject invoice via UI.

    Body:
    {
      "approver": "user:alice",
      "reason": "wrong vendor / duplicate / mismatch"
    }
    Result: sets status -> REJECTED and appends workflow step.
    """
    body = payload or {}
    approver = body.get("approver", "ui:unknown")
    reason = body.get("reason", "")

    db = get_db()

    # fetch invoice
    rec = db.invoices.find_one({"_id": invoice_id})
    if not rec:
        # try fallbacks
        rec = db.invoices.find_one({"header.invoice_ref": invoice_id}) or db.invoices.find_one({"header.invoice_number.value": invoice_id})
        if not rec:
            raise HTTPException(status_code=404, detail="invoice_not_found")
        invoice_id = rec.get("_id")

    step = {
        "agent": "HumanApprovalUI",
        "type": "reject",
        "invoice_id": invoice_id,
        "actor": approver,
        "result": {"action": "reject", "reason": reason},
        "timestamp": _now_iso()
    }

    try:
        _append_workflow_step_and_update_status(db, invoice_id, step, new_status="REJECTED")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"reject_failed: {e}")

    updated = db.invoices.find_one({"_id": invoice_id})
    if isinstance(updated.get("_id"), ObjectId):
        updated["_id"] = str(updated["_id"])
    return JSONResponse({"ok": True, "invoice": updated})
