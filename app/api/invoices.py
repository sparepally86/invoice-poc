# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException
from app.storage.mongo_client import get_db
from fastapi.responses import JSONResponse
from typing import Dict, Any
import uuid
import datetime

router = APIRouter()

# In-memory store for POC
INVOICE_STORE: Dict[str, Dict[str, Any]] = {}

def ensure_minimal_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the payload has a minimal set of fields so the stored record
    is consistent. We intentionally do NOT enforce full Pydantic validation
    here so the frontend/Capture can post partial canonical JSON during POC.
    """
    payload = dict(payload)  # shallow copy to avoid mutating caller

    # header
    header = payload.get("header", {})
    if not isinstance(header, dict):
        header = {}
    header.setdefault("invoice_number", {"value": header.get("invoice_number", {}).get("value") if isinstance(header.get("invoice_number"), dict) else None, "confidence": 0.0})
    header.setdefault("invoice_date", {"value": header.get("invoice_date", {}).get("value") if isinstance(header.get("invoice_date"), dict) else None, "confidence": 0.0})
    header.setdefault("grand_total", {"value": header.get("grand_total", {}).get("value") if isinstance(header.get("grand_total"), dict) else 0.0, "confidence": 0.0})
    payload["header"] = header

    # vendor
    vendor = payload.get("vendor", {})
    if not isinstance(vendor, dict):
        vendor = {"name_raw": None}
    vendor.setdefault("vendor_id", vendor.get("vendor_id"))
    vendor.setdefault("name_raw", vendor.get("name_raw"))
    payload["vendor"] = vendor

    # lines
    lines = payload.get("lines")
    if not isinstance(lines, list):
        payload["lines"] = []

    # validation and ml_metadata placeholders
    payload.setdefault("validation", {})
    payload.setdefault("ml_metadata", {})

    return payload

@router.post("/incoming")
async def incoming_invoice(payload: dict = Body(...)):
    """
    Accept canonical invoice JSON, store it, and enqueue a processing task.
    """
    db = get_db()
    header = payload.get("header", {})
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or f"INV-{uuid.uuid4().hex[:8]}"
    invoice_id = invoice_ref

    now = datetime.datetime.utcnow().isoformat() + "Z"
    invoice_doc = {
        **payload,
        "_id": invoice_id,
        "status": "RECEIVED",
        "_workflow": {"steps": []},
        "created_at": now
    }

    # store invoice
    try:
        db.invoices.insert_one(invoice_doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store invoice: {e}")

    # create a processing task
    task_doc = {
        "type": "process_invoice",
        "invoice_id": invoice_id,
        "status": "queued",
        "created_at": now
    }
    db.tasks.insert_one(task_doc)

    return {"invoice_id": invoice_id, "status": "queued"}

# app/api/tasks.py  (or wherever your /invoices/{invoice_id} route is)
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db

router = APIRouter()

@router.get("/invoices/{invoice_id}", response_class=JSONResponse)
async def get_invoice(invoice_id: str):
    """
    Robust invoice fetch:
     1) try _id
     2) fallback to header.invoice_ref
     3) fallback to header.invoice_number.value (common Captures)
    Returns full invoice doc (including _workflow.steps).
    """
    db = get_db()

    # 1) try by _id
    rec = db.invoices.find_one({"_id": invoice_id})
    if rec:
        # ensure _id is serializable
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    # 2) fallback: header.invoice_ref
    rec = db.invoices.find_one({"header.invoice_ref": invoice_id})
    if rec:
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    # 3) fallback: header.invoice_number.value (some capture outputs use nested value)
    rec = db.invoices.find_one({"header.invoice_number.value": invoice_id})
    if rec:
        rec["_id"] = str(rec.get("_id"))
        return JSONResponse(rec)

    # not found
    raise HTTPException(status_code=404, detail=f"invoice not found for id/ref: {invoice_id}")
