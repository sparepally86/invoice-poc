# app/api/invoices.py
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
import uuid
from app.models.schemas import CanonicalInvoice

router = APIRouter()

# Simple in-memory store for POC
# NOTE: in production, replace with persistent DB (Mongo/Postgres)
INVOICE_STORE: Dict[str, dict] = {}

@router.post("/incoming", response_class=JSONResponse)
async def incoming(payload: CanonicalInvoice = Body(...)):
    """
    Accept canonical invoice JSON (validated by Pydantic CanonicalInvoice),
    store it in memory with a generated invoice_id and metadata, and
    return a simple receipt indicating agentic processing is pending.
    """
    # Generate stable invoice id (short)
    invoice_id = "inv-" + uuid.uuid4().hex[:12]

    record = payload.dict()
    record["_meta"] = {
        "invoice_id": invoice_id,
        "status_code": 1,
        "message": "received - queued for agentic automation"
    }

    # Persist in-memory
    INVOICE_STORE[invoice_id] = record

    return JSONResponse({"invoice_id": invoice_id, "status_code": 1, "message": "received - queued for agentic automation"})
    

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """
    Retrieve the stored canonical invoice JSON (for inspection).
    """
    rec = INVOICE_STORE.get(invoice_id)
    if not rec:
        raise HTTPException(status_code=404, detail="invoice not found")
    return rec
