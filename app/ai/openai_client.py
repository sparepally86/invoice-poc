# app/ai/openai_client.py
import os
import logging
import time
import json
from typing import List, Optional, Dict, Any

from openai import OpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Initialize OpenAI v1+ client
_client = None
if OPENAI_API_KEY:
    _client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY not set. Embedding calls will fail if invoked.")


class OpenAIClient:
    """
    OpenAI LLM client wrapper for chat completions using the v1+ SDK.
    Provides a consistent interface expected by get_llm_client().
    """

    def __init__(self, api_key: Optional[str] = None, base: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self._client = None
        if self.api_key:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        else:
            logger.warning("OpenAIClient: No API key provided. LLM calls will fail.")

    def call_llm(self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Call OpenAI chat completions API and return a structured response.
        """
        if not self._client:
            raise RuntimeError("OpenAI API key not configured")

        start = time.time()
        try:
            messages = [{"role": "user", "content": prompt}]
            result = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = result.choices[0].message.content or ""
            parsed = None
            if schema:
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = {"raw": content}
            else:
                parsed = {"raw": content}

            usage = None
            if result.usage:
                usage = {
                    "prompt_tokens": result.usage.prompt_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "total_tokens": result.usage.total_tokens,
                }

            return {
                "provider": "openai",
                "model": self.model,
                "text": content,
                "raw": content,
                "parsed": parsed,
                "usage": usage,
                "meta": {
                    "usage": usage,
                    "elapsed_ms": int((time.time() - start) * 1000)
                }
            }
        except Exception as e:
            logger.exception("OpenAI LLM call failed: %s", e)
            return {"provider": "openai", "error": str(e)}


def embed_text(text: str, model: str | None = None, retry: int = 2) -> List[float]:
    """
    Return embedding vector for the given text using OpenAI Embeddings API.
    Retries on transient errors.
    """
    mdl = model or EMBEDDING_MODEL
    if not _client:
        raise RuntimeError("OpenAI API key not configured for embedding")

    # Minimal retry loop
    for attempt in range(retry + 1):
        try:
            resp = _client.embeddings.create(model=mdl, input=text)
            emb = resp.data[0].embedding
            return emb
        except Exception as e:
            logger.exception("OpenAI embedding error (attempt %s/%s): %s", attempt + 1, retry + 1, e)
            if attempt < retry:
                time.sleep(1 + attempt * 1.5)
                continue
            raise
