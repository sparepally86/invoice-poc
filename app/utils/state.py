# app/utils/state.py
from typing import Optional, Dict, Any
from datetime import datetime
from app.storage.mongo_client import get_db

# Canonical statuses (use these strings across the app)
# You can extend this as needed.
ALLOWED_STATUSES = [
    "RECEIVED",    # initial
    "VALIDATED",
    "MATCHED",
    "EXCEPTION",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "POSTED",
]

# Minimal status transition rules (source -> allowed targets)
STATUS_TRANSITIONS = {
    "RECEIVED": {"VALIDATED", "EXCEPTION"},
    "VALIDATED": {"MATCHED", "EXCEPTION", "PENDING_APPROVAL"},
    "MATCHED": {"PENDING_APPROVAL", "APPROVED", "EXCEPTION"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "EXCEPTION"},
    "APPROVED": {"POSTED"},
    "REJECTED": set(),
    "POSTED": set(),
    "EXCEPTION": {"PENDING_APPROVAL", "REJECTED"},
}

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def update_invoice_status(db, invoice_id: str, new_status: str, actor: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
    """
    Update invoice status in a canonical way:
      - validate new_status is allowed (if possible)
      - persist a status-change entry into invoice._workflow.steps
      - set invoice.status to new_status
      - return the status-change record

    Parameters:
      - db: pymongo database (get_db())
      - invoice_id: invoice _id
      - new_status: string from ALLOWED_STATUSES (or any free-form if required)
      - actor: optional string indicating who/what changed the status (e.g., "Orchestrator", "User:john")
      - note: optional human note

    Behavior:
      - If current status exists, test allowed transition; if not allowed, still perform update
        but mark transition_allowed=False in the record (so it's auditable).
      - Always append a `_workflow.steps` entry of type 'status_change'.
    """
    invoices = db.invoices
    rec = invoices.find_one({"_id": invoice_id})
    if not rec:
        raise RuntimeError(f"invoice not found: {invoice_id}")

    current = rec.get("status")
    transition_allowed = True
    if current:
        allowed = STATUS_TRANSITIONS.get(current, None)
        if allowed is not None and new_status not in allowed and new_status != current:
            transition_allowed = False

    ts = _now_iso()
    actor = actor or "system"
    step = {
        "agent": "StatusManager",
        "type": "status_change",
        "invoice_id": invoice_id,
        "from": current,
        "to": new_status,
        "allowed": transition_allowed,
        "actor": actor,
        "note": note,
        "timestamp": ts
    }

    # persist: push workflow step and set status atomically (two ops)
    invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": step}, "$set": {"status": new_status, "updated_at": ts}})

    return step
