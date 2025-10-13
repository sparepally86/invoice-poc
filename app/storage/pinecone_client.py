# app/storage/pinecone_client.py
"""
Pinecone vector client wrapper.

Provides:
- PineconeClient(api_key, environment, index_name, embed_fn=None)
  - upsert(id, text, metadata=None)
  - search(query_or_vector, k=5, filter=None) -> list of {id, score, excerpt, metadata}
Notes:
- Requires `pinecone-client` package (pip install "pinecone-client").
- embed_fn: callable(text)->{"embedding":[...]} - if not provided we call OpenAI embed via app.ai.openai_client.OpenAIClient
"""

from typing import Optional, Any, List, Dict
import os
import math

# We'll support both Pinecone v3 (preferred) and v2 (fallback)
_pc_v3 = None
_pc_v2 = None
try:
    from pinecone import Pinecone as _PineconeV3  # v3 SDK
    _pc_v3 = _PineconeV3
except Exception:
    try:
        import pinecone as _pinecone_v2  # v2 SDK
        _pc_v2 = _pinecone_v2
    except Exception:
        _pc_v2 = None

from app.config import PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME
from app.ai.openai_client import OpenAIClient

class PineconeClient:
    def __init__(self, api_key: Optional[str] = None, environment: Optional[str] = None, index_name: Optional[str] = None, embed_fn: Optional[Any] = None):
        if _pc_v3 is None and _pc_v2 is None:
            raise RuntimeError("pinecone package not installed. Install 'pinecone' (v3) or 'pinecone-client' (v2).")

        self.api_key = api_key or PINECONE_API_KEY
        self.environment = environment or PINECONE_ENVIRONMENT
        self.index_name = index_name or PINECONE_INDEX_NAME
        if not self.api_key or not self.index_name:
            raise RuntimeError("Pinecone not configured: set PINECONE_API_KEY and PINECONE_INDEX_NAME (and PINECONE_ENVIRONMENT for v2)")

        self._version = None
        if _pc_v3 is not None:
            # v3 client doesn't use environment at init
            pc = _pc_v3(api_key=self.api_key)
            self.index = pc.Index(self.index_name)
            self._version = 3
        else:
            # v2 requires environment
            if not self.environment:
                raise RuntimeError("PINECONE_ENVIRONMENT is required for pinecone-client v2.x")
            _pc_v2.init(api_key=self.api_key, environment=self.environment)
            self.index = _pc_v2.Index(self.index_name)
            self._version = 2

        # embed_fn should return {"embedding": [...]} when called with text
        self.embed_fn = embed_fn or (OpenAIClient().embed_text)

    def upsert(self, id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Upsert a single chunk into Pinecone. metadata is stored as-is.
        """
        emb_res = self.embed_fn(text)
        vector = emb_res.get("embedding")
        if vector is None:
            raise RuntimeError("Embedding generation failed for upsert")
        if self._version == 3:
            # v3 expects dicts with id/values/metadata
            self.index.upsert(vectors=[{"id": id, "values": vector, "metadata": metadata or {}}])
        else:
            # v2 expects tuples (id, values, metadata)
            self.index.upsert(vectors=[(id, vector, metadata or {})])
        return {"id": id, "metadata": metadata}

    def search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Accepts a query string (we will embed it) and returns top-k matches.
        Returns list of dicts: {id, score, excerpt, metadata}
        """
        # embed the query
        emb_res = self.embed_fn(query)
        vector = emb_res.get("embedding")
        if vector is None:
            return []
        # Pinecone query
        if self._version == 3:
            res = self.index.query(vector=vector, top_k=k, include_metadata=True, include_values=False, filter=filter)
            matches = res.get("matches", [])
        else:
            res = self.index.query(queries=[vector], top_k=k, include_metadata=True, include_values=False, filter=filter)
            matches = res.get("results", [])[0].get("matches", []) if res.get("results") else res.get("matches", [])
        out = []
        for m in matches:
            md = m.get("metadata", {}) if isinstance(m, dict) else {}
            out.append({
                "id": m.get("id"),
                "score": m.get("score"),
                "excerpt": (md or {}).get("chunk_text_preview") or (md or {}).get("text") or "",
                "metadata": md
            })
        return out
