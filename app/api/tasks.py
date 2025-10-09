# app/api/tasks.py
from fastapi import APIRouter, Query
from app.storage.mongo_client import get_db
from fastapi.responses import JSONResponse
from fastapi import Body, Path
from bson import ObjectId

router = APIRouter()

@router.get("/tasks")
async def list_tasks(status: str = Query(None)):
    db = get_db()
    q = {}
    if status:
        q["status"] = status
    docs = list(db.tasks.find(q).sort([("created_at", -1)]).limit(200))
    # Convert ObjectId etc. (we mainly use string _id if we set invoice_id as _id)
    results = []
    for d in docs:
        d["_id"] = str(d.get("_id"))
        results.append(d)
    return JSONResponse(results)

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    db = get_db()
    doc = db.invoices.find_one({"_id": invoice_id})
    if not doc:
        return JSONResponse({"error": "not_found"}, status_code=404)
    # convert _id if needed
    doc["_id"] = str(doc.get("_id"))
    return JSONResponse(doc)

@router.get("/tasks/pending")
async def list_pending_tasks():
    db = get_db()
    docs = list(db.tasks.find({"status": "pending", "type": "human_review"}).sort([("created_at", -1)]).limit(200))
    results = []
    for d in docs:
        d["_id"] = str(d.get("_id"))
        results.append(d)
    return JSONResponse(results)

@router.post("/tasks/{task_id}/action")
async def act_on_task(task_id: str = Path(...), action: dict = Body(...)):
    """
    action payload example:
    { "action": "approve" } or
    { "action": "reject", "reason": "wrong price" } or
    { "action": "edit", "invoice": { ...updated invoice JSON... } }
    """
    db = get_db()
    task = db.tasks.find_one({"_id": ObjectId(task_id)}) if ObjectId.is_valid(task_id) else db.tasks.find_one({"_id": task_id})
    if not task:
        return JSONResponse({"error": "task_not_found"}, status_code=404)

    act = action.get("action")
    if act == "approve":
        # mark task resolved and set invoice status APPROVED (or continue pipeline)
        db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": "resolved", "action":"approve", "resolved_at": datetime.datetime.utcnow().isoformat()+"Z"}})
        db.invoices.update_one({"_id": task["invoice_id"]}, {"$set": {"status": "APPROVED"}})
        return JSONResponse({"ok": True})
    elif act == "reject":
        reason = action.get("reason", "rejected_by_user")
        db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": "resolved", "action":"reject", "reason": reason, "resolved_at": datetime.datetime.utcnow().isoformat()+"Z"}})
        db.invoices.update_one({"_id": task["invoice_id"]}, {"$set": {"status": "REJECTED"}})
        return JSONResponse({"ok": True})
    elif act == "edit":
        new_invoice = action.get("invoice")
        if not new_invoice:
            return JSONResponse({"error": "missing_invoice"}, status_code=400)
        # overwrite invoice doc (simple approach for POC)
        db.invoices.replace_one({"_id": task["invoice_id"]}, new_invoice)
        # mark task resolved and requeue processing
        db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": "resolved", "action":"edit", "resolved_at": datetime.datetime.utcnow().isoformat()+"Z"}})
        # create a new processing task to re-run pipeline
        db.tasks.insert_one({"type": "process_invoice", "invoice_id": task["invoice_id"], "status": "queued", "created_at": datetime.datetime.utcnow().isoformat()+"Z"})
        return JSONResponse({"ok": True})
    else:
        return JSONResponse({"error":"unknown_action"}, status_code=400)