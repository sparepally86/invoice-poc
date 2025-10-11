# app/ai/openai_client.py
"""
OpenAI client wrapper (lightweight, HTTP-based).

Provides:
- OpenAIClient(api_key, base, model)
  - .model (str)
  - .call_llm(prompt, max_tokens=..., temperature=...) -> dict or text
  - .embed_text(text, model="text-embedding-3-small") -> { "embedding": [...], "model": "..."}
Notes:
- Uses OPENAI_API_KEY and OPENAI_API_BASE (from app.config) when available.
- Returns provider usage info if OpenAI returns it.
"""

import os
import requests
import json
from typing import Any, Dict, Optional, List

from app.config import OPENAI_API_KEY, OPENAI_API_BASE

DEFAULT_CHAT_MODEL = "gpt-4o"  # change to a model you want
DEFAULT_EMBED_MODEL = "text-embedding-3-small"

class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None, base: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.base = base or (OPENAI_API_BASE or "https://api.openai.com/v1")
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured (OPENAI_API_KEY)")
        self.model = model or DEFAULT_CHAT_MODEL
        # simple session
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def call_llm(self, prompt: str, max_tokens: int = 300, temperature: float = 0.0) -> Dict[str, Any]:
        """
        Calls OpenAI Chat Completions (chat/completions).
        Returns dict with keys: text (string), usage (if present), raw (full response)
        """
        url = f"{self.base.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = self._session.post(url, data=json.dumps(payload), timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text}")
        j = resp.json()
        # try to extract text
        try:
            text = ""
            if "choices" in j and len(j["choices"]) > 0:
                # join if multiple
                text = "".join([c.get("message", {}).get("content", "") for c in j["choices"]])
        except Exception:
            text = str(j)
        out = {"text": text, "raw": j}
        if "usage" in j:
            out["usage"] = j["usage"]
        return out

    def embed_text(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Calls OpenAI embeddings endpoint.
        Returns {"embedding": [...], "model": ..., "raw": <resp>}
        """
        mdl = model or DEFAULT_EMBED_MODEL
        url = f"{self.base.rstrip('/')}/embeddings"
        payload = {"model": mdl, "input": text}
        resp = self._session.post(url, data=json.dumps(payload), timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI embeddings error {resp.status_code}: {resp.text}")
        j = resp.json()
        # embeddings endpoint returns 'data' array
        emb = None
        try:
            emb = j.get("data", [])[0].get("embedding")
        except Exception:
            emb = None
        out = {"embedding": emb, "model": mdl, "raw": j}
        return out
