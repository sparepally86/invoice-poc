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


def retrieve(query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Retrieve top-k similar chunks for the query using vector_client.search().
    Returns list of results with fields: id, score, excerpt, metadata.
    """
    vc = get_vector_client()
    results = vc.search(query, k=k, filter=filter)
    return results


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
