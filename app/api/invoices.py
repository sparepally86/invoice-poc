# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException
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

@router.post("/incoming", response_class=JSONResponse)
async def incoming(payload: Dict[str, Any] = Body(...)):
    """
    Accept any JSON representing the canonical invoice (flexible), ensure minimal structure,
    store in-memory, and return a simple receipt indicating agentic processing is pending.
    """
    if not isinstance(payload, dict):
        return JSONResponse({"error":"expected a JSON object"}, status_code=400)

    # Ensure minimal structure and defaults
    record = ensure_minimal_structure(payload)

    # Generate an invoice id and add metadata
    invoice_id = "inv-" + uuid.uuid4().hex[:12]
    record_meta = {
        "invoice_id": invoice_id,
        "status_code": 1,
        "message": "received - queued for agentic automation",
        "received_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    record["_meta"] = record_meta

    # Store the record
    INVOICE_STORE[invoice_id] = record

    return JSONResponse({"invoice_id": invoice_id, "status_code": 1, "message": "received - queued for agentic automation"})

@router.get("/invoices/{invoice_id}", response_class=JSONResponse)
async def get_invoice(invoice_id: str):
    rec = INVOICE_STORE.get(invoice_id)
    if not rec:
        raise HTTPException(status_code=404, detail="invoice not found")
    return rec
