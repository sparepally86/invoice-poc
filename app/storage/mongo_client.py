# app/storage/mongo_client.py
from pymongo import MongoClient
import os
from typing import Optional
from urllib.parse import urlparse

MONGO_URI = os.environ.get("MONGODB_URI")
MONGO_DBNAME = os.environ.get("MONGODB_DB")  # optional override
_default_db_name = "invoice_poc"

_client: Optional[MongoClient] = None
_db = None

def _extract_db_from_uri(uri: str) -> Optional[str]:
    try:
        parsed = urlparse(uri)
        if parsed.path and parsed.path != "/":
            return parsed.path.lstrip("/")
    except Exception:
        return None
    return None

def get_db():
    """
    Returns a pymongo Database instance.
    Expects MONGODB_URI to be set in env variables.
    Optionally MONGODB_DB can override the DB name.
    If neither present in env var nor URI, fallback to default 'invoice_poc'.
    """
    global _client, _db
    # Use explicit None check — pymongo Database objects are not truthy/falsey.
    if _db is not None:
        return _db

    if not MONGO_URI:
        raise RuntimeError("MONGODB_URI not set")

    if _client is None:
        _client = MongoClient(MONGO_URI, tls=True)

    # Determine DB name
    db_name = MONGO_DBNAME or _extract_db_from_uri(MONGO_URI) or _default_db_name

    _db = _client[db_name]
    return _db

def close_client():
    global _client
    if _client:
        _client.close()
        _client = None
