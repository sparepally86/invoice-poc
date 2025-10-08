# app/api/masterdata.py
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
from app.storage.mongo_client import get_db
import datetime
import uuid

router = APIRouter()

# --- Vendors ----
@router.post("/vendors", response_class=JSONResponse)
async def create_vendor(payload: Dict[str, Any] = Body(...)):
    """
    Create a vendor document. If vendor_id provided, we use it; otherwise auto-generate.
    """
    db = get_db()
    coll = db.get_collection("vendors")
    vendor_id = payload.get("vendor_id") or f"V{uuid.uuid4().hex[:8]}"
    payload["vendor_id"] = vendor_id
    payload["_meta"] = {"created_at": datetime.datetime.utcnow().isoformat() + "Z"}
    # use vendor_id as _id for easy lookup
    doc = {**payload, "_id": vendor_id}
    coll.insert_one(doc)
    return {"vendor_id": vendor_id}

@router.get("/vendors/{vendor_id}")
async def read_vendor(vendor_id: str):
    db = get_db()
    coll = db.get_collection("vendors")
    doc = coll.find_one({"_id": vendor_id}, {"_id":0})
    if not doc:
        raise HTTPException(status_code=404, detail="vendor not found")
    return doc

@router.get("/vendors")
async def list_vendors(limit: int = Query(50, le=100), skip: int = 0):
    db = get_db()
    coll = db.get_collection("vendors")
    docs = list(coll.find({}, {"_id":0}).skip(skip).limit(limit))
    return {"count": len(docs), "vendors": docs}

@router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, payload: Dict[str, Any] = Body(...)):
    db = get_db()
    coll = db.get_collection("vendors")
    res = coll.update_one({"_id": vendor_id}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="vendor not found")
    return {"vendor_id": vendor_id, "updated": res.modified_count}

@router.delete("/vendors/{vendor_id}")
async def delete_vendor(vendor_id: str):
    db = get_db()
    coll = db.get_collection("vendors")
    res = coll.delete_one({"_id": vendor_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="vendor not found")
    return {"vendor_id": vendor_id, "deleted": True}


# --- Purchase Orders (POs) ----
@router.post("/pos", response_class=JSONResponse)
async def create_po(payload: Dict[str, Any] = Body(...)):
    db = get_db()
    coll = db.get_collection("pos")
    po_number = payload.get("po_number") or f"PO-{uuid.uuid4().hex[:8]}"
    payload["po_number"] = po_number
    payload["_meta"] = {"created_at": datetime.datetime.utcnow().isoformat() + "Z"}
    doc = {**payload, "_id": po_number}
    coll.insert_one(doc)
    return {"po_number": po_number}

@router.get("/pos/{po_number}")
async def read_po(po_number: str):
    db = get_db()
    coll = db.get_collection("pos")
    doc = coll.find_one({"_id": po_number}, {"_id":0})
    if not doc:
        raise HTTPException(status_code=404, detail="po not found")
    return doc

@router.get("/pos")
async def list_pos(limit: int = Query(50, le=200), skip: int = 0):
    db = get_db()
    coll = db.get_collection("pos")
    docs = list(coll.find({}, {"_id":0}).skip(skip).limit(limit))
    return {"count": len(docs), "pos": docs}

@router.put("/pos/{po_number}")
async def update_po(po_number: str, payload: Dict[str, Any] = Body(...)):
    db = get_db()
    coll = db.get_collection("pos")
    res = coll.update_one({"_id": po_number}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="po not found")
    return {"po_number": po_number, "updated": res.modified_count}

@router.delete("/pos/{po_number}")
async def delete_po(po_number: str):
    db = get_db()
    coll = db.get_collection("pos")
    res = coll.delete_one({"_id": po_number})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="po not found")
    return {"po_number": po_number, "deleted": True}
