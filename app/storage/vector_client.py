# app/storage/vector_client.py
"""
Simple Vector client with in-memory fallback.

API:
- upsert(doc_id: str, text: str, metadata: dict) -> dict
- search(query: str, k: int = 5, filter: dict = None) -> list[dict]

This provides a deterministic, dependency-free fallback for dev/POC.
A production implementation should replace the internals with a real vector DB (Weaviate, Pinecone, Chroma, etc.)
"""

from typing import Optional, Dict, Any, List
import threading
import time
import re

_lock = threading.Lock()

class InMemoryVectorClient:
    def __init__(self):
        # store docs as dict: id -> {text, metadata, created_at}
        self._store: Dict[str, Dict[str, Any]] = {}

    def upsert(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Insert or replace a document.
        """
        if metadata is None:
            metadata = {}
        with _lock:
            self._store[doc_id] = {
                "id": doc_id,
                "text": text,
                "metadata": dict(metadata),
                "created_at": time.time()
            }
        return {"ok": True, "id": doc_id}

    def _score_text_match(self, query: str, text: str) -> float:
        """
        Deterministic, simple similarity: number of shared tokens / unique tokens.
        Lowercased, punctuation-stripped.
        """
        def tokens(s: str):
            return set(re.findall(r"\w+", s.lower()))
        q = tokens(query)
        t = tokens(text)
        if not q or not t:
            return 0.0
        inter = q.intersection(t)
        # Jaccard-like score (deterministic)
        score = len(inter) / max(1, len(q.union(t)))
        return float(score)

    def search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Return top-k documents with deterministic score ordering.
        Each result: {id, score, excerpt, metadata}
        filter param is a simple metadata filter (all key-values must match).
        """
        with _lock:
            items = list(self._store.values())

        # apply simple metadata filter if provided
        if filter:
            def keep(d):
                md = d.get("metadata", {})
                for kf, vf in filter.items():
                    if md.get(kf) != vf:
                        return False
                return True
            items = [d for d in items if keep(d)]

        scored = []
        for d in items:
            s = self._score_text_match(query, d.get("text", "") or "")
            if s > 0:
                excerpt = d.get("text","")
                # deterministic excerpt: first 160 chars
                excerpt = excerpt[:160]
                scored.append({"id": d["id"], "score": s, "excerpt": excerpt, "metadata": d.get("metadata", {})})
        # sort descending by score then by created_at so deterministic tie-break
        scored.sort(key=lambda x: (-x["score"], x.get("id")))
        return scored[:k]

# Exported client factory
_default_client = None

def get_vector_client(provider: Optional[str] = None):
    """
    For POC we ignore provider and return in-memory client.
    A real implementation would inspect provider and create a remote client.
    """
    global _default_client
    if _default_client is None:
        _default_client = InMemoryVectorClient()
    return _default_client
