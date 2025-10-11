from datetime import datetime
from typing import Optional

# Example assumes pymongo MongoClient instance `db` is available in your app context.

TERMINAL_INVOICE_STATES = {"READY_FOR_POSTING", "REJECTED", "POSTED", "CANCELLED"}

def sse_broadcast(event: dict):
    """Application should wire this to its SSE/Websocket broadcasting implementation.
    This is a stub used for unit tests / local dev; replace with your realtime layer.
    """
    # Example: push into Redis pub/sub or server-sent events manager
    print("SSE BROADCAST:", event)

def complete_task_action(db, task_id: str, action: str, user: Optional[str] = None, notes: Optional[str] = None):
    """Atomically mark task completed and set invoice status.

    Args:
        db: pymongo database object
        task_id: string task id (assumed to be stored as string in tasks.invoice_id)
        action: 'approve' or 'reject'
        user: optional username performing the action
        notes: optional free-text notes

    Returns:
        dict with task_id and new invoice_status
    Raises:
        ValueError if task or invoice not found or invalid action
    """
    if action not in ("approve", "reject"):
        raise ValueError("invalid action")

    # Find task
    task = db.tasks.find_one({"_id": task_id})
    if not task:
        raise ValueError("task not found")

    invoice_id = task.get("invoice_id")
    if not invoice_id:
        raise ValueError("task has no invoice_id")

    invoice = db.invoices.find_one({"_id": invoice_id})
    if not invoice:
        raise ValueError("invoice not found")

    new_invoice_status = "READY_FOR_POSTING" if action == "approve" else "REJECTED"

    # Update task -> mark completed
    db.tasks.update_one(
        {"_id": task_id, "status": {"$ne": "completed"}},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "action": action,
            "action_by": user,
            "notes": notes,
        }}
    )

    # Update invoice status and append workflow step
    db.invoices.update_one(
        {"_id": invoice_id},
        {
            "$set": {"status": new_invoice_status},
            "$push": {"_workflow.steps": {
                "agent": "HITL",
                "status": new_invoice_status,
                "action": action,
                "timestamp": datetime.utcnow(),
                "task_id": task_id,
                "actor": user,
                "notes": notes,
            }}
        }
    )

    # Broadcast SSE / websocket events for realtime UI update
    sse_broadcast({
        "type": "task:update",
        "task_id": task_id,
        "status": "completed",
    })
    sse_broadcast({
        "type": "invoice:update",
        "invoice_id": invoice_id,
        "status": new_invoice_status,
    })

    return {"task_id": task_id, "invoice_status": new_invoice_status}