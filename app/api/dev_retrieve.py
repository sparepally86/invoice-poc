# app/api/dev_retrieve.py
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from app.agents.retrieval import index_document, retrieve
from app.storage.vector_client import get_vector_client

router = APIRouter()

@router.post("/api/v1/dev/retrieve/index", response_class=JSONResponse)
async def dev_retrieve_index(payload: Dict[str, Any] = Body(...)):
    """
    Index a document into the in-memory retrieval store.
    Body: {"id": "doc-1", "text": "...", "metadata": {...}}
    """
    doc_id = payload.get("id") or payload.get("doc_id")
    text = payload.get("text") or payload.get("content") or ""
    metadata = payload.get("metadata", {})
    if not doc_id or not text:
        return JSONResponse({"ok": False, "error": "missing id or text"}, status_code=400)
    res = index_document(doc_id, text, metadata=metadata)
    return JSONResponse({"ok": True, "indexed_chunks": res})


@router.get("/api/v1/dev/retrieve/search", response_class=JSONResponse)
async def dev_retrieve_search(q: str = Query(...), k: int = Query(5), loc: Optional[str] = Query(None)):
    """
    Search indexed chunks by query. Example: /api/v1/dev/retrieve/search?q=laptop&k=3
    Optional loc used as metadata filter: loc=mumbai
    """
    filt = None
    if loc:
        filt = {"loc": loc}
    res = retrieve(q, k=k, filter=filt)
    return JSONResponse({"ok": True, "query": q, "results": res})
