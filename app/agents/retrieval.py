# app/agents/retrieval.py
"""
RetrievalAgent & embedding hooks (skeleton for Phase B).

Provides:
- chunk_text(text, chunk_size=512, overlap=50)
- embed_text(text)                # NOOP / placeholder embedding
- index_document(doc_id, text, metadata=None)
- retrieve(query, k=5, filter=None)

This is intentionally simple and uses the in-memory vector_client for POC.
Replace embed_text() with a real embedding call when ready.
"""

from typing import List, Dict, Optional, Any, Iterable, Tuple
import hashlib
import math
import re

from app.storage.vector_client import get_vector_client
from app.ai.llm_client import get_llm_client

# Configurable defaults
DEFAULT_CHUNK_SIZE = 400  # characters (simple char-based chunker for POC)
DEFAULT_OVERLAP = 50      # characters overlap between chunks


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> List[str]:
    """
    Chunk text into overlapping windows. This simple implementation splits on whitespace
    and constructs chunks ~chunk_size characters long with overlap.
    """
    if not text:
        return []
    # Normalize whitespace
    s = re.sub(r"\s+", " ", text).strip()
    if len(s) <= chunk_size:
        return [s]
    chunks = []
    start = 0
    while start < len(s):
        end = start + chunk_size
        chunk = s[start:end]
        chunks.append(chunk)
        if end >= len(s):
            break
        start = max(0, end - overlap)
    return chunks


def _hash_embedding_placeholder(text: str) -> str:
    """Deterministic placeholder 'embedding' (hex string); not a vector."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return h


def embed_text(text: str) -> Dict[str, Any]:
    """
    Placeholder embedding function.
    Returns a dict with an 'embedding' key for future compatibility.
    Replace this with a call to a real embedding provider (OpenAI, sentence-transformers, etc.)
    """
    # If a provider is set to noop, produce a deterministic fingerprint.
    client = get_llm_client()
    provider = (client.provider or "noop").lower()
    if provider == "noop":
        return {"embedding": _hash_embedding_placeholder(text), "provider": "noop"}
    # Example hook: if provider supports embeddings, call it here.
    # For now, fallback to the hash placeholder.
    return {"embedding": _hash_embedding_placeholder(text), "provider": provider}


def index_document(doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None,
                   chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> List[Dict[str, Any]]:
    """
    Chunk the text and upsert each chunk into the vector DB.
    Returns list of upserted chunk metadata.
    """
    vc = get_vector_client()
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    results = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}__chunk__{i}"
        emb = embed_text(chunk)  # placeholder
        md = dict(metadata or {})
        md.update({"parent_id": doc_id, "chunk_index": i, "chunk_text_preview": chunk[:200], "embedding_meta": emb})
        # The in-memory vector client stores text and metadata; production vector DB expects embedding vectors.
        vc.upsert(chunk_id, chunk, metadata=md)
        results.append({"chunk_id": chunk_id, "score": None, "metadata": md})
    return results


def retrieve(query: str, k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
    """
    Retrieve top-k similar chunks for the query using vector_client.search().
    Returns list of results with fields: id, score, excerpt, metadata.
    
    Note: Different vector clients have different search signatures:
    - InMemoryVectorClient: search(query, k, filter)
    - PineconeClient: search(query, k, min_score)
    """
    vc = get_vector_client()
    try:
        results = vc.search(query, k=k, min_score=min_score)
    except TypeError:
        results = vc.search(query, k=k)
    return results


def _invoice_to_query_text(invoice: Dict[str, Any]) -> str:
    """
    Convert invoice JSON to a query string for retrieval.
    Extracts key fields to create a meaningful search query.
    """
    parts = []
    header = invoice.get("header", {}) or {}
    
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id")
    if invoice_ref:
        parts.append(str(invoice_ref))
    
    vendor = header.get("vendor") or header.get("vendor_name") or header.get("supplier")
    if vendor:
        parts.append(f"vendor:{vendor}")
    
    amount = header.get("amount") or header.get("total") or header.get("invoice_amount")
    if amount:
        parts.append(f"amount:{amount}")
    
    po_number = header.get("po_number") or header.get("po") or header.get("po_reference")
    if po_number:
        parts.append(f"PO:{po_number}")
    
    lines = invoice.get("lines") or invoice.get("items") or []
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        if isinstance(first, dict):
            desc = first.get("description") or first.get("desc") or ""
            if desc:
                parts.append(str(desc)[:100])
    
    query = " ".join([p for p in parts if p]).strip()
    if not query:
        query = str(invoice.get("_id", "invoice"))
    return query[:1000]


def _normalize_hit(hit: Dict[str, Any], min_score: float = 0.0) -> Optional[Dict[str, Any]]:
    """
    Normalize a retrieval hit to the expected output format:
    {
        id,
        score,
        metadata: {
            type,          // "invoice" | "feedback" | "doc"
            source_id,
            text_preview
        }
    }
    """
    score = hit.get("score", 0.0)
    if score < min_score:
        return None
    
    raw_metadata = hit.get("metadata", {}) or {}
    
    doc_type = raw_metadata.get("type") or raw_metadata.get("doc_type") or "doc"
    source_id = (
        raw_metadata.get("source_id") or 
        raw_metadata.get("source_invoice") or
        raw_metadata.get("parent_id") or 
        hit.get("id", "")
    )
    text_preview = (
        raw_metadata.get("text_preview") or 
        raw_metadata.get("chunk_text_preview") or 
        hit.get("excerpt", "")
    )
    if len(text_preview) > 200:
        text_preview = text_preview[:200] + "..."
    
    return {
        "id": hit.get("id", ""),
        "score": score,
        "metadata": {
            "type": doc_type,
            "source_id": source_id,
            "text_preview": text_preview
        }
    }


def search_invoice(invoice: Dict[str, Any], k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
    """
    Search for similar documents based on the invoice content.
    
    Args:
        invoice: Full invoice JSON document
        k: Number of results to return (default 5)
        min_score: Minimum score threshold for results (default 0.0)
    
    Returns:
        List of hits with normalized format:
        {
            id,
            score,
            metadata: {
                type,          // "invoice" | "feedback" | "doc"
                source_id,
                text_preview
            }
        }
    """
    query = _invoice_to_query_text(invoice)
    raw_results = retrieve(query, k=k, min_score=min_score)
    
    normalized = []
    for hit in raw_results:
        norm = _normalize_hit(hit, min_score=min_score)
        if norm:
            normalized.append(norm)
    
    return normalized


def reindex_documents(docs: Iterable[Tuple[str, str, Optional[Dict[str, Any]]]],
                      chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> int:
    """
    Accepts an iterable of (doc_id, text, metadata) and indexes them.
    Returns number of chunks indexed.
    """
    total = 0
    for doc_id, text, metadata in docs:
        res = index_document(doc_id, text, metadata=metadata, chunk_size=chunk_size, overlap=overlap)
        total += len(res)
    return total
