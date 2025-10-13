# app/storage/pinecone_client.py
"""
Pinecone client wrapper used by get_vector_client().
This constructor accepts optional args so callers can pass
explicit values (useful for factory or tests), but also falls
back to environment variables.
"""

import os
import logging
from typing import Any, Dict, List

import openai
import pinecone

logger = logging.getLogger(__name__)

class PineconeClient:
    def __init__(
        self,
        api_key: str | None = None,
        env: str | None = None,
        index_name: str | None = None,
        embed_model: str | None = None,
    ):
        # Accept injected values or read from environment
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = env or os.getenv("PINECONE_ENVIRONMENT")
        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "invoice-poc")
        self.embed_model = embed_model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        if not self.api_key or not self.environment:
            raise ValueError("Pinecone API key and environment must be provided")

        # Init OpenAI API for embeddings (embedding calls use OpenAI)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            openai.api_key = openai_api_key
        else:
            # We do not raise here because some tests may mock embeddings or
            # use other embedding backends. But warn for production.
            logger.warning("OPENAI_API_KEY not set - embeddings will fail if used")

        # Initialize pinecone and the index
        pinecone.init(api_key=self.api_key, environment=self.environment)
        try:
            self._index = pinecone.Index(self.index_name)
        except Exception as e:
            # Re-raise with context so logs show the intended index/env
            logger.exception("Failed to open Pinecone index '%s' in env '%s': %s",
                             self.index_name, self.environment, e)
            raise

        logger.info("PineconeClient initialized for index=%s env=%s", self.index_name, self.environment)

    def embed_text(self, text: str) -> List[float]:
        """
        Create an embedding for the given text using OpenAI.
        Caller should handle OpenAI errors / rate limits.
        """
        if not getattr(openai, "api_key", None):
            raise RuntimeError("OpenAI API key is not configured for embeddings")

        resp = openai.Embedding.create(model=self.embed_model, input=text)
        return resp["data"][0]["embedding"]

    def upsert(self, id: str, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Upsert a single vector (embedding created from `text`) into the index.
        """
        if metadata is None:
            metadata = {}
        vec = self.embed_text(text)
        self._index.upsert(vectors=[(id, vec, metadata)])
        return {"ok": True, "id": id}

    def upsert_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upsert multiple items. Each item should be {id, text, metadata}.
        """
        vectors = []
        for it in items:
            text = it.get("text") or it.get("chunk_text") or ""
            vec = self.embed_text(text)
            vectors.append((it["id"], vec, it.get("metadata", {})))
        self._index.upsert(vectors=vectors)
        return {"ok": True, "count": len(vectors)}

    def search(self, query: str, k: int = 3, min_score: float | None = None) -> List[Dict[str, Any]]:
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
            idx_meta = pinecone.describe_index(self.index_name)
            return {"ok": True, "index": idx_meta}
        except Exception as e:
            logger.exception("describe_index failed: %s", e)
            return {"ok": False, "error": str(e)}
