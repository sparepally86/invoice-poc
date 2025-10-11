# app/api/dev_reindex_feedback.py
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import asyncio
from app.storage.mongo_client import get_db
from app.agents.retrieval import index_document

router = APIRouter()

def _to_thread(fn, *a, **kw):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*a, **kw))

@router.post("/api/v1/dev/reindex-feedback", response_class=JSONResponse)
async def dev_reindex_feedback(limit: Optional[int] = Query(None), dry_run: Optional[bool] = Query(False)):
    """
    Trigger reindex of feedback into the in-memory vector client.
    Query params:
      limit (optional) - max feedback docs to process
      dry_run (bool) - if true do not write, only report
    """
    db = get_db()
    # fetch feedback docs
    cursor = await _to_thread(db.feedback.find, {})
    docs = await _to_thread(list, cursor.sort("created_at", 1).limit(limit if limit else 1000))
    processed = 0
    created_chunks = 0
    for fb in docs:
        invoice_id = fb.get("invoice_id")
        if not invoice_id:
            continue
        invoice = await _to_thread(db.invoices.find_one, {"_id": invoice_id})
        explain_step = None
        # find latest explain step
        steps = (invoice.get("_workflow", {}) or {}).get("steps") if invoice else None
        if steps:
            for s in reversed(steps):
                if s.get("agent") == "ExplainAgent":
                    explain_step = s
                    break
        text_parts = []
        inv_ref = (invoice.get("header", {}) or {}).get("invoice_ref") or invoice_id
        text_parts.append(f"Invoice: {inv_ref}")
        if explain_step and explain_step.get("result"):
            text_parts.append(f"Explanation: {explain_step.get('result', {}).get('explanation')}")
        text_parts.append(f"Feedback: {fb.get('verdict')} - {fb.get('notes','')}")
        text_blob = "\n".join([p for p in text_parts if p])
        doc_id = f"feedback::{fb.get('_id')}"
        metadata = {"source":"feedback","invoice_id":invoice_id,"feedback_id":str(fb.get("_id")),"verdict":fb.get("verdict")}
        if not dry_run:
            chunks = index_document(doc_id, text_blob, metadata=metadata)
            created_chunks += len(chunks)
        processed += 1
    return JSONResponse({"ok": True, "processed": processed, "created_chunks": created_chunks, "dry_run": bool(dry_run)})
