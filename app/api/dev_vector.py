# app/api/dev_vector.py
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from app.storage.vector_client import get_vector_client

router = APIRouter()

@router.post("/dev/vector/upsert", response_class=JSONResponse)
async def dev_vector_upsert(payload: Dict[str, Any] = Body(...)):
    """
    Dev endpoint to upsert a document into the in-memory vector client.
    Body JSON:
    {
      "id": "doc-1",
      "text": "some text to index",
      "metadata": {"type":"invoice", "loc":"mumbai"}
    }
    """
    vc = get_vector_client()
    doc_id = payload.get("id") or payload.get("doc_id")
    text = payload.get("text") or payload.get("content") or ""
    metadata = payload.get("metadata") or {}
    if not doc_id:
        return JSONResponse({"ok": False, "error": "missing id"}, status_code=400)
    res = vc.upsert(doc_id, text, metadata=metadata)
    return JSONResponse(res)

@router.get("/dev/vector/search", response_class=JSONResponse)
async def dev_vector_search(q: str = Query(...), k: int = Query(5), loc: Optional[str] = Query(None)):
    """
    Dev endpoint to search the in-memory vector client.
    Query params:
      q - query text
      k - top k results (optional)
      loc - optional metadata filter (example)
    Example:
      /api/v1/dev/vector/search?q=laptop&k=3&loc=mumbai
    """
    vc = get_vector_client()
    filter_md = None
    if loc:
        filter_md = {"loc": loc}
    results = vc.search(q, k=k, filter=filter_md)
    return JSONResponse({"ok": True, "query": q, "k": k, "results": results})

# --- Compatibility aliases (for docs/tools expecting /dev/retrieve/*) ---
@router.post("/dev/retrieve/index", response_class=JSONResponse)
async def dev_retrieve_index(payload: Dict[str, Any] = Body(...)):
  """
  Compatibility alias for indexing a doc. Mirrors /dev/vector/upsert but returns
  an "indexed_chunks" field to match older examples.

  Body JSON:
  {
    "id": "doc-1",
    "text": "some text",
    "metadata": { ... }
  }
  """
  vc = get_vector_client()
  doc_id = payload.get("id") or payload.get("doc_id")
  text = payload.get("text") or payload.get("content") or ""
  metadata = payload.get("metadata") or {}
  if not doc_id:
    return JSONResponse({"ok": False, "error": "missing id"}, status_code=400)
  res = vc.upsert(doc_id, text, metadata=metadata)
  # In-memory client doesn't chunk; report 1 chunk if there's any text
  chunk_count = 1 if (text or "").strip() else 0
  return JSONResponse({"ok": True, "id": res.get("id", doc_id), "indexed_chunks": chunk_count})

@router.get("/dev/retrieve/search", response_class=JSONResponse)
async def dev_retrieve_search(q: str = Query(...), k: int = Query(5), loc: Optional[str] = Query(None)):
  """
  Compatibility alias for searching, mirroring /dev/vector/search.
  """
  vc = get_vector_client()
  filter_md = None
  if loc:
    filter_md = {"loc": loc}
  results = vc.search(q, k=k, filter=filter_md)
  return JSONResponse({"ok": True, "query": q, "k": k, "results": results})
