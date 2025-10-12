# app/config.py
import os
from typing import Optional
"""
Optional .env support: if python-dotenv is installed and a .env file exists,
load it so local development can manage env vars via a file instead of shell.
This is a no-op if python-dotenv is not installed.
"""
try:
    from dotenv import load_dotenv  # type: ignore
    # Allow overriding path via ENV_FILE; default to ".env" in project root
    _env_file = os.environ.get("ENV_FILE", ".env")
    load_dotenv(dotenv_path=_env_file, override=False)
except Exception:
    pass

def _getenv(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    if v is None:
        return default
    return v

# Provider selection
LLM_PROVIDER = _getenv("LLM_PROVIDER", "noop").lower()
VECTOR_PROVIDER = _getenv("VECTOR_PROVIDER", "inmemory").lower()

# OpenAI
OPENAI_API_KEY = _getenv("OPENAI_API_KEY")
OPENAI_API_BASE = _getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

# Pinecone
PINECONE_API_KEY = _getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = _getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = _getenv("PINECONE_INDEX_NAME", "invoice-poc")

# Weaviate
WEAVIATE_URL = _getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = _getenv("WEAVIATE_API_KEY")

# Local LLM
LOCAL_LLM_URL = _getenv("LOCAL_LLM_URL")
LOCAL_LLM_MODEL = _getenv("LOCAL_LLM_MODEL", "llama2")

# Telemetry
TELEMETRY_WRITE = _getenv("TELEMETRY_WRITE", "true").lower() in ("1", "true", "yes")

# Rate limiter
LLM_RATE_LIMIT_PER_MINUTE = int(_getenv("LLM_RATE_LIMIT_PER_MINUTE", "60"))
LLM_RATE_LIMIT_CAPACITY = int(_getenv("LLM_RATE_LIMIT_CAPACITY", "60"))

# Deployment env
DEPLOY_ENV = _getenv("DEPLOY_ENV", "development")
