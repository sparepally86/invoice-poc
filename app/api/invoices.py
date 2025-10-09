# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db
from typing import Dict, Any
import uuid
from datetime import datetime

router = APIRouter()


def ensure_minimal_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the payload has a minimal set of fields so the stored record
    is consistent. This keeps POC ingestion tolerant.
    """
    payload = dict(payload)  # shallow copy

    # header normalization (support multiple shapes)
    header = payload.get("header") or {}
    if not isinstance(header, dict):
        header = {}

    # invoice_ref can be present as header.invoice_ref (string) or header.invoice_number dict
    inv_ref = header.get("invoice_ref") or None
    inv_number = header.get("invoice_number")
    if isinstance(inv_number, dict):
        inv_number_val = inv_number.get("value")
    else:
        inv_number_val = inv_number

    header.setdefault("invoice_ref", inv_ref or inv_number_val)
    # keep nested shapes for legacy capture shape
    if not isinstance(header.get("invoice_number"), dict):
        header.setdefault("invoice_number", {"value": header.get("invoice_ref"), "confidence": 0.0})
    if not isinstance(header.get("invoice_date"), dict):
        header.setdefault("invoice_date", {"value": header.get("invoice_date") if header.get("invoice_date") else None, "confidence": 0.0})
    if not isinstance(header.get("grand_total"), dict):
        header.setdefault("grand_total", {"value": header.get("grand_total") or header.get("amount") or 0.0, "confidence": 0.0})

    payload["header"] = header

    # vendor
    vendor = payload.get("vendor") or {}
    if not isinstance(vendor, dict):
        vendor = {}
    vendor.setdefault("vendor_id", vendor.get("vendor_id") or vendor.get("_id"))
    vendor.setdefault("name_raw", vendor.get("name_raw") or vendor.get("name"))
    payload["vendor"] = vendor

    # lines/items support both 'lines' and 'items'
    if "lines" in payload:
        if not isinstance(payload["lines"], list):
            payload["lines"] = []
    else:
        # normalize to 'lines' if 'items' provided
        items = payload.get("items")
        if isinstance(items, list):
            payload["lines"] = items
        else:
            payload.setdefault("lines", [])

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
