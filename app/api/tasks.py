# app/api/tasks.py
from fastapi import APIRouter, Query
from app.storage.mongo_client import get_db
from fastapi.responses import JSONResponse

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
