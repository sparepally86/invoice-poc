# app/ai/openai_client.py
import os
import logging
import time
from typing import List

import openai

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not set. Embedding calls will fail if invoked.")
else:
    openai.api_key = OPENAI_API_KEY

def embed_text(text: str, model: str | None = None, retry: int = 2) -> List[float]:
    """
    Return embedding vector for the given text using OpenAI Embeddings API.
    Retries on transient errors.
    """
    mdl = model or EMBEDDING_MODEL
    if not getattr(openai, "api_key", None):
        raise RuntimeError("OpenAI API key not configured for embedding")

    # Minimal retry loop
    for attempt in range(retry + 1):
        try:
            resp = openai.Embedding.create(model=mdl, input=text)
            emb = resp["data"][0]["embedding"]
            return emb
        except Exception as e:
            logger.exception("OpenAI embedding error (attempt %s/%s): %s", attempt + 1, retry + 1, e)
            if attempt < retry:
                time.sleep(1 + attempt * 1.5)
                continue
            raise
