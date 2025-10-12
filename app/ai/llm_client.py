# app/ai/llm_client.py
import os
import time
import json
import logging
from typing import Optional, Dict, Any

from app.config import LLM_PROVIDER, OPENAI_API_KEY, OPENAI_API_BASE, LOCAL_LLM_URL, LOCAL_LLM_MODEL

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Minimal LLM wrapper with a 'noop' provider for local tests and a
    pluggable OpenAI implementation when you add keys.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, timeout: int = 30):
        self.provider = provider or os.getenv("LLM_PROVIDER", "noop")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.timeout = timeout
        # optional API key for cloud provider
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")

    def call_llm(self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Call LLM and return a dict. If provider == 'noop', return a deterministic response.
        schema = optional JSON schema hint (not enforced here)
        """
        start = time.time()
        if self.provider.lower() == "noop":
            # deterministic local response for tests/development
            resp = {
                "provider": "noop",
                "model": "noop-model",
                "text": f"[NOOP ECHO] {prompt[:500]}",
                "meta": {"elapsed_ms": int((time.time() - start) * 1000)}
            }
            logger.debug("LLM noop response generated")
            return resp

        # OpenAI example (if you enable)
        if self.provider.lower() in ("openai", "gpt"):
            try:
                import openai
                openai.api_key = self.api_key
                messages = [{"role": "user", "content": prompt}]
                # use ChatCompletion for structured responses; adjust per provider
                result = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout,
                )
                content = result.choices[0].message.get("content", "")
                # attempt to parse JSON if schema expected
                parsed = None
                if schema:
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        parsed = {"raw": content}
                else:
                    parsed = {"raw": content}
                resp = {
                    "provider": "openai",
                    "model": self.model,
                    "raw": content,
                    "parsed": parsed,
                    "meta": {
                        "usage": getattr(result, "usage", None),
                        "elapsed_ms": int((time.time() - start) * 1000)
                    }
                }
                return resp
            except Exception as e:
                logger.exception("LLM call failed: %s", e)
                return {"provider": self.provider, "error": str(e)}
        else:
            raise NotImplementedError(f"LLM provider '{self.provider}' not implemented")

# Replace the old convenience singleton/selector with a config-driven selector
def get_llm_client():
    provider = (LLM_PROVIDER or "noop").lower()
    if provider == "openai":
        # small wrapper that returns an object with .model and .call_llm(prompt,...)
        from app.ai.openai_client import OpenAIClient
        return OpenAIClient(api_key=OPENAI_API_KEY, base=OPENAI_API_BASE)
    if provider == "local":
        from app.ai.local_llm_client import LocalLLMClient
        return LocalLLMClient(url=LOCAL_LLM_URL, model=LOCAL_LLM_MODEL)
    # fallback to built-in generic client in noop mode (no external calls)
    return LLMClient(provider="noop")
