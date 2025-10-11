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

try:
    import pinecone
except Exception:
    pinecone = None

from app.config import PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME
from app.ai.openai_client import OpenAIClient

class PineconeClient:
    def __init__(self, api_key: Optional[str] = None, environment: Optional[str] = None, index_name: Optional[str] = None, embed_fn: Optional[Any] = None):
        if pinecone is None:
            raise RuntimeError("pinecone-client package not installed (pip install pinecone-client)")
        self.api_key = api_key or PINECONE_API_KEY
        self.environment = environment or PINECONE_ENVIRONMENT
        self.index_name = index_name or PINECONE_INDEX_NAME
        if not self.api_key or not self.environment or not self.index_name:
            raise RuntimeError("Pinecone not configured: set PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME")
        pinecone.init(api_key=self.api_key, environment=self.environment)
        self.index = pinecone.Index(self.index_name)
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
        # pinecone upsert expects list of tuples
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
        res = self.index.query(queries=[vector], top_k=k, include_metadata=True, include_values=False, filter=filter)
        # res['results'][0]['matches'] is typical shape
        matches = res.get("results", [])[0].get("matches", []) if res.get("results") else res.get("matches", [])
        out = []
        for m in matches:
            out.append({
                "id": m.get("id"),
                "score": m.get("score"),
                "excerpt": (m.get("metadata") or {}).get("chunk_text_preview") or (m.get("metadata") or {}).get("text") or "",
                "metadata": m.get("metadata", {})
            })
        return out
