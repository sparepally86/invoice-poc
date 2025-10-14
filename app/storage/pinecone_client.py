# app/storage/pinecone_client.py
"""
Pinecone client wrapper used by get_vector_client().
This constructor accepts optional args so callers can pass
explicit values (useful for factory or tests), but also falls
back to environment variables.
"""

import os
import logging
from typing import Optional, Union
from typing import Any, Dict, List

from pinecone import Pinecone
from app.ai.openai_client import embed_text

logger = logging.getLogger(__name__)

class PineconeClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        env: Optional[str] = None,
        index_name: Optional[str] = None,
        embed_model: Optional[str] = None,
    ):
        # Accept injected values or read from environment
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = env or os.getenv("PINECONE_ENVIRONMENT")  # optional on v3
        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "invoice-poc")
        self.embed_model = embed_model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        # v3: only API key is required; environment is optional (ignored by SDK)
        if not self.api_key:
            raise ValueError("Pinecone API key must be provided")

        # Check if OpenAI API key is available for embeddings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set - embeddings will fail if used")

        # Initialize pinecone (v3)
        self._pc = Pinecone(api_key=self.api_key)
        try:
            self._index = self._pc.Index(self.index_name)
        except Exception as e:
            logger.exception("Failed to open Pinecone index '%s' (env=%s): %s",
                             self.index_name, self.environment or "n/a", e)
            raise

        logger.info("PineconeClient initialized index=%s (env=%s)", self.index_name, self.environment or "n/a")

    def embed_text(self, text: str) -> List[float]:
        """
        Create an embedding for the given text using OpenAI.
        Caller should handle OpenAI errors / rate limits.
        """
        if not self.openai_api_key:
            raise RuntimeError("OpenAI API key is not configured for embeddings")

        return embed_text(text, model=self.embed_model)

    def upsert(self, id: str, text: str, metadata: Dict[str, Any] | None = None, embedding: List[float] | None = None) -> Dict[str, Any]:
        """
        Upsert a single vector (embedding created from `text`) into the index.
        If 'embedding' is provided it will be used directly; otherwise the server will call OpenAI.
        """
        if metadata is None:
            metadata = {}

        if embedding is None:
            # Use OpenAI embedding hook (raise descriptive error if not configured)
            if not self.openai_api_key:
                raise RuntimeError("OpenAI API key is not configured for embeddings")
            embedding = self.embed_text(text)

        try:
            # New SDK and old SDK both support upsert(this shape)
            self._index.upsert(vectors=[(id, embedding, metadata)])
        except Exception as e:
            logger.exception("Upsert failed for id=%s: %s", id, e)
            raise
        return {"ok": True, "id": id}


    def upsert_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upsert multiple items. Each item should be {id, text, metadata, embedding?}.
        If an item provides 'embedding' it will be used; otherwise the embedding is computed.
        """
        vectors = []
        for it in items:
            text = it.get("text") or it.get("chunk_text") or ""
            emb = it.get("embedding")
            if emb is None:
                if not self.openai_api_key:
                    raise RuntimeError("OpenAI API key not configured for batch embeddings")
                emb = self.embed_text(text)
            vectors.append((it["id"], emb, it.get("metadata", {})))
        self._index.upsert(vectors=vectors)
        return {"ok": True, "count": len(vectors)}


    def search(self, query: str, k: int = 3, min_score: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Semantic search for the query string. Returns list of hits with id, score, metadata.
        """
        qvec = self.embed_text(query)
        # include_metadata True to get metadata stored with vector
        resp = self._index.query(vector=qvec, top_k=k, include_metadata=True)
        hits = []
        matches = getattr(resp, "matches", None) or resp.get("matches", [])
        for m in matches:
            score = float(m.score) if hasattr(m, "score") else float(m["score"])
            if min_score is not None and score < min_score:
                continue
            hits.append({
                "id": m.id if hasattr(m, "id") else m["id"],
                "score": round(score, 6),
                "metadata": getattr(m, "metadata", None) or m.get("metadata", {})
            })
        return hits

    def describe_index(self) -> Dict[str, Any]:
        try:
            idx_meta = self._pc.describe_index(self.index_name)
            return {"ok": True, "index": idx_meta}
        except Exception as e:
            logger.exception("describe_index failed: %s", e)
            return {"ok": False, "error": str(e)}
