# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db, get_next_invoice_id
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from bson import ObjectId
from starlette.responses import StreamingResponse
import json
import asyncio
from app.utils.normalize_invoice import ensure_minimal_structure
from app.utils.schema_validator import validate_received_invoice
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# helper synchronous wrappers for PyMongo calls (run via asyncio.to_thread)
def _find_one_sync(coll, q):
    return coll.find_one(q)

def _count_sync(coll, q=None):
    if q is None:
        q = {}
    return coll.count_documents(q)

def _now_iso():
    """Return current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"

# SSE helper
def format_sse(event: str, data: dict):
    payload = f"event: {event}\n"
    payload += f"data: {json.dumps(data, default=str)}\n\n"
    return payload


# ================================================================================
# 1️⃣  POST /api/invoices — Create DRAFT Invoice
# ================================================================================
@router.post("/invoices", response_class=JSONResponse)
async def create_draft_invoice(payload: dict = Body(...)):
    """
    Create a new DRAFT invoice with minimal information.
    
    Behavior:
    - Generate invoice_id (sequential)
    - Generate trace_id if not present
    - Set status = DRAFT
    - Store minimal invoice stub (identity, source, status, audit timestamps)
    - Ignore header / lines if present (do not validate them at this stage)
    - Return invoice_id to caller
    
    This endpoint does NOT trigger Orchestrator.
    It is idempotent-safe: retries with same data do not regenerate invoice_id.
    
    Request body (minimal):
    {
        "vendor": {...},
        "source": {...},
        "document": {...},
        "trace_id": "optional"  # If not present, will be generated
    }
    
    Returns:
    {
        "invoice_id": 123,
        "trace_id": "...",
        "status": "DRAFT"
    }
    """
    db = get_db()
    
    # Generate next sequential invoice_id
    try:
        invoice_id = get_next_invoice_id()
    except Exception as e:
        logger.exception("Failed to generate invoice_id")
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice_id: {e}")
    
    # Generate trace_id if not present
    trace_id = payload.get("trace_id") or str(uuid.uuid4())
    
    now = _now_iso()
    
    # Build minimal DRAFT invoice document
    invoice_doc = {
        "_id": invoice_id,
        "invoice_id": invoice_id,
        "trace_id": trace_id,
        "status": "DRAFT",
        "vendor": payload.get("vendor"),
        "source": payload.get("source"),
        "document": payload.get("document"),
        # Note: header, lines, validation etc. are NOT required at DRAFT stage
        "_workflow": {"steps": []},
        "created_at": now,
        "updated_at": now,
    }
    
    # Store invoice
    try:
        db.invoices.insert_one(invoice_doc)
        logger.info("Created DRAFT invoice: invoice_id=%s trace_id=%s", invoice_id, trace_id)
    except Exception as e:
        logger.exception("Failed to store DRAFT invoice")
        raise HTTPException(status_code=500, detail=f"Failed to store invoice: {e}")
    
    return JSONResponse({
        "invoice_id": invoice_id,
        "trace_id": trace_id,
        "status": "DRAFT"
    })


# ================================================================================
# 2️⃣  PUT /api/invoices/{invoice_id} — Submit DRAFT to RECEIVED
# ================================================================================
@router.put("/invoices/{invoice_id}", response_class=JSONResponse)
async def submit_draft_invoice(invoice_id: int, payload: dict = Body(...)):
    """
    Transition an invoice from DRAFT to RECEIVED.
    
    Behavior:
    - Look up existing invoice by invoice_id
    - Validate:
      - invoice exists
      - current status is DRAFT
    - Merge provided payload into existing invoice
    - Generate trace_id if missing
    - Validate invoice against canonical schema rules for RECEIVED
    - Set status = RECEIVED
    - Update audit timestamps
    - Create orchestration task to trigger agents
    
    Important:
    - Do NOT regenerate invoice_id
    - Do NOT allow transition from any status other than DRAFT
    - Reject PUT if invoice is already RECEIVED or beyond
    
    Request body (full invoice data):
    {
        "vendor": {...},
        "source": {...},
        "document": {...},
        "header": {...},
        "lines": [...],
        "validation": {...},
        ...
    }
    
    Returns: Updated invoice document
    """
    db = get_db()
    
    # Look up existing invoice
    existing = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
    
    if not existing:
        logger.warning("PUT /invoices: invoice not found: invoice_id=%s", invoice_id)
        raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_id}")
    
    # Validate current status is DRAFT
    current_status = existing.get("status")
    if current_status != "DRAFT":
        logger.warning(
            "PUT /invoices: invalid status transition: invoice_id=%s current_status=%s",
            invoice_id, current_status
        )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status} to RECEIVED. Only DRAFT → RECEIVED allowed."
        )
    
    # Merge payload into existing invoice
    now = _now_iso()
    existing["trace_id"] = existing.get("trace_id") or payload.get("trace_id") or str(uuid.uuid4())
    existing.update(payload)
    existing["status"] = "RECEIVED"
    existing["updated_at"] = now
    
    # Validate invoice against canonical schema for RECEIVED status
    is_valid, errors = validate_received_invoice(existing)
    if not is_valid:
        logger.warning(
            "PUT /invoices: schema validation failed: invoice_id=%s errors=%s",
            invoice_id, errors
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Schema validation failed",
                "fields": errors
            }
        )
    
    # Persist updated invoice
    try:
        result = await asyncio.to_thread(
            db.invoices.replace_one,
            {"_id": invoice_id},
            existing
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_id}")
        logger.info("Submitted invoice to RECEIVED: invoice_id=%s trace_id=%s", invoice_id, existing.get("trace_id"))
    except Exception as e:
        logger.exception("Failed to update invoice to RECEIVED: invoice_id=%s", invoice_id)
        raise HTTPException(status_code=500, detail=f"Failed to update invoice: {e}")
    
    # Create orchestration task to trigger agents
    # (Orchestrator will only process RECEIVED invoices)
    try:
        task_doc = {
            "type": "process_invoice",
            "invoice_id": invoice_id,
            "status": "queued",
            "created_at": now
        }
        await asyncio.to_thread(db.tasks.insert_one, task_doc)
        logger.info("Created orchestration task for invoice: invoice_id=%s", invoice_id)
    except Exception as e:
        logger.exception("Failed to create orchestration task: invoice_id=%s", invoice_id)
        # Invoice was already persisted, so don't fail the entire request
        # Just log and let the user know
        raise HTTPException(status_code=500, detail=f"Invoice updated but task creation failed: {e}")
    
    # Return updated invoice
    if isinstance(existing.get("_id"), ObjectId):
        existing["_id"] = str(existing["_id"])
    return JSONResponse(existing)


# ================================================================================
# 3️⃣  POST /api/invoices/submit — Create RECEIVED Directly (UI Convenience)
# ================================================================================
@router.post("/invoices/submit", response_class=JSONResponse)
async def submit_received_invoice(payload: dict = Body(...)):
    """
    Create a RECEIVED invoice directly in one step (UI convenience).
    
    This is a faster path for the UI to submit invoices that are already complete
    and don't require a two-step DRAFT → RECEIVED flow.
    
    Behavior:
    - Generate invoice_id (sequential)
    - Generate trace_id if not present
    - Validate payload against RECEIVED schema rules
    - Set status = RECEIVED
    - Persist invoice in one step
    - Create orchestration task (Orchestrator will be triggered)
    
    This endpoint is ONLY for UI / internal use.
    
    Request body (complete invoice):
    {
        "vendor": {...},
        "source": {...},
        "document": {...},
        "header": {...},
        "lines": [...],
        "validation": {...},
        "trace_id": "optional"
    }
    
    Returns:
    {
        "invoice_id": 123,
        "trace_id": "...",
        "status": "RECEIVED"
    }
    """
    db = get_db()
    
    # Generate invoice_id
    try:
        invoice_id = get_next_invoice_id()
    except Exception as e:
        logger.exception("Failed to generate invoice_id")
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice_id: {e}")
    
    # Generate trace_id if not present
    trace_id = payload.get("trace_id") or str(uuid.uuid4())
    
    now = _now_iso()
    
    # Build RECEIVED invoice document
    invoice_doc = {
        "_id": invoice_id,
        "invoice_id": invoice_id,
        "trace_id": trace_id,
        "status": "RECEIVED",
        "vendor": payload.get("vendor"),
        "source": payload.get("source"),
        "document": payload.get("document"),
        "header": payload.get("header"),
        "lines": payload.get("lines"),
        "validation": payload.get("validation"),
        "_workflow": {"steps": []},
        "created_at": now,
        "updated_at": now,
    }
    
    # Validate invoice against canonical schema for RECEIVED status
    is_valid, errors = validate_received_invoice(invoice_doc)
    if not is_valid:
        logger.warning(
            "POST /invoices/submit: schema validation failed: invoice_id=%s errors=%s",
            invoice_id, errors
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Schema validation failed",
                "fields": errors
            }
        )
    
    # Store invoice
    try:
        db.invoices.insert_one(invoice_doc)
        logger.info("Created RECEIVED invoice (direct): invoice_id=%s trace_id=%s", invoice_id, trace_id)
    except Exception as e:
        logger.exception("Failed to store RECEIVED invoice")
        raise HTTPException(status_code=500, detail=f"Failed to store invoice: {e}")
    
    # Create orchestration task to trigger agents
    try:
        task_doc = {
            "type": "process_invoice",
            "invoice_id": invoice_id,
            "status": "queued",
            "created_at": now
        }
        db.tasks.insert_one(task_doc)
        logger.info("Created orchestration task for invoice: invoice_id=%s", invoice_id)
    except Exception as e:
        logger.exception("Failed to create orchestration task: invoice_id=%s", invoice_id)
        # Invoice was already persisted, so don't fail the entire request
        raise HTTPException(status_code=500, detail=f"Invoice created but task creation failed: {e}")
    
    return JSONResponse({
        "invoice_id": invoice_id,
        "trace_id": trace_id,
        "status": "RECEIVED"
    })


# ================================================================================
# Legacy POST /api/invoices/incoming (Backward Compatibility)
# ================================================================================
@router.post("/incoming", response_class=JSONResponse)
async def incoming_invoice(payload: dict = Body(...)):
    """
    Legacy endpoint: Accept canonical invoice JSON and create RECEIVED invoice directly.
    
    This endpoint is kept for backward compatibility.
    New code should use POST /api/invoices/submit instead.
    
    Behavior:
    - Normalize payload minimally
    - Generate invoice_id
    - Set status = RECEIVED
    - Create orchestration task
    
    Returns: { "invoice_id": ..., "status": "queued" }
    """
    db = get_db()

    # Normalize payload minimally
    payload = ensure_minimal_structure(payload)
    
    # Generate next sequential invoice_id (atomic, concurrency-safe)
    try:
        invoice_id = get_next_invoice_id()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice_id: {e}")
    
    now = _now_iso()
    trace_id = str(uuid.uuid4())

    invoice_doc = {
        **payload,
        "_id": invoice_id,
        "invoice_id": invoice_id,  # Store invoice_id in document for API consumption
        "trace_id": trace_id,
        "status": "RECEIVED",
        "_workflow": {"steps": []},
        "created_at": now,
        "updated_at": now,
    }

    # store invoice
    try:
        db.invoices.insert_one(invoice_doc)
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
    1) try _id (as numeric)
    2) fallback to header.invoice_ref
    3) fallback to header.invoice_number.value (common Capture shape)
    Returns full invoice doc (including _workflow.steps).
    """
    db = get_db()

    # 1) try by _id (handle both numeric and string)
    try:
        numeric_id = int(invoice_id)
        rec = await asyncio.to_thread(db.invoices.find_one, {"_id": numeric_id})
        if rec:
            if isinstance(rec.get("_id"), ObjectId):
                rec["_id"] = str(rec["_id"])
            return JSONResponse(rec)
    except (ValueError, TypeError):
        # Not a numeric ID, continue to fallbacks
        pass

    # 2) fallback: header.invoice_ref
    rec = await asyncio.to_thread(db.invoices.find_one, {"header.invoice_ref": invoice_id})
    if rec:
        if isinstance(rec.get("_id"), ObjectId):
            rec["_id"] = str(rec["_id"])
        return JSONResponse(rec)

    # 3) fallback: header.invoice_number.value
    rec = await asyncio.to_thread(db.invoices.find_one, {"header.invoice_number.value": invoice_id})
    if rec:
        if isinstance(rec.get("_id"), ObjectId):
            rec["_id"] = str(rec["_id"])
        return JSONResponse(rec)

    raise HTTPException(status_code=404, detail=f"invoice not found for id/ref: {invoice_id}")


def _list_invoices_sync(flt: dict, limit: int):
    """Synchronous helper to fetch invoices (intended for asyncio.to_thread)."""
    db = get_db()
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
    return docs


@router.get("/invoices", response_class=JSONResponse)
async def list_invoices(limit: int = Query(50, ge=1, le=1000), q: Optional[str] = Query(None)):
    """
    Simple list endpoint for invoices.
    - ?limit=50  (max 1000)
    - ?q=TERM    (matches _id, header.invoice_ref, header.po_number, header.po)
    Returns: { "items": [ {..invoice..}, ... ] }
    """
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

    logger.info("list_invoices called: limit=%s q=%s", limit, q)
    try:
        # Run blocking DB call in thread pool to avoid blocking the event loop
        docs = await asyncio.to_thread(_list_invoices_sync, flt, limit)
        return JSONResponse({"items": docs})
    except Exception as e:
        logger.exception("list_invoices failed")
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

    # after updating invoice status, mark any pending/queued HITL tasks for this invoice as resolved
    try:
        db.tasks.update_many(
            {"invoice_id": invoice_id, "status": {"$in": ["pending", "queued"]}},
            {"$set": {"status": "done", "resolved_at": _now_iso()}}
        )
    except Exception:
        # non-fatal: don't block approve flow if tasks collection op fails
        pass

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

    # after updating invoice status, mark any pending/queued HITL tasks for this invoice as resolved
    try:
        db.tasks.update_many(
            {"invoice_id": invoice_id, "status": {"$in": ["pending", "queued"]}},
            {"$set": {"status": "done", "resolved_at": _now_iso()}}
        )
    except Exception:
        # non-fatal: don't block reject flow if tasks collection op fails
        pass

    updated = db.invoices.find_one({"_id": invoice_id})
    if isinstance(updated.get("_id"), ObjectId):
        updated["_id"] = str(updated["_id"])
    return JSONResponse({"ok": True, "invoice": updated})
