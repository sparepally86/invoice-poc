# app/api/approvals.py
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from app.storage.mongo_client import get_db
from app.utils.state import update_invoice_status
from typing import Dict, Any
import datetime

router = APIRouter()

@router.post("/invoices/{invoice_id}/approve", response_class=JSONResponse)
async def approve_invoice(invoice_id: str, body: Dict[str, Any] = Body(...)):
    """
    Approve an invoice. body: {"approver":"user:alice","comment":"ok"}
    """
    db = get_db()
    rec = db.invoices.find_one({"_id": invoice_id})
    if not rec:
        raise HTTPException(status_code=404, detail="invoice not found")

    # mark invoice approved
    actor = body.get("approver", "user:unknown")
    note = body.get("comment", "approved")
    update_invoice_status(db, invoice_id, "APPROVED", actor, note=note)

    # mark any pending approval tasks for this invoice as done
    now = datetime.datetime.utcnow().isoformat() + "Z"
    db.tasks.update_many({"invoice_id": invoice_id, "type": "approval", "status": "pending"}, {"$set": {"status": "done", "finished_at": now}})

    # create a small audit step for approval
    step = {"agent": "ApprovalAPI", "invoice_id": invoice_id, "status": "approved", "result": {"approver": actor, "comment": note}, "timestamp": now}
    db.invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": step}})

    return JSONResponse({"invoice_id": invoice_id, "status": "APPROVED"})

@router.post("/invoices/{invoice_id}/reject", response_class=JSONResponse)
async def reject_invoice(invoice_id: str, body: Dict[str, Any] = Body(...)):
    db = get_db()
    rec = db.invoices.find_one({"_id": invoice_id})
    if not rec:
        raise HTTPException(status_code=404, detail="invoice not found")

    actor = body.get("approver", "user:unknown")
    note = body.get("comment", "rejected")
    update_invoice_status(db, invoice_id, "REJECTED", actor, note=note)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    db.tasks.update_many({"invoice_id": invoice_id, "type": "approval", "status": "pending"}, {"$set": {"status": "done", "finished_at": now}})

    step = {"agent": "ApprovalAPI", "invoice_id": invoice_id, "status": "rejected", "result": {"approver": actor, "comment": note}, "timestamp": now}
    db.invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": step}})

    return JSONResponse({"invoice_id": invoice_id, "status": "REJECTED"})
