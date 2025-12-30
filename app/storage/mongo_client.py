# app/storage/mongo_client.py
from pymongo import MongoClient
import os
from typing import Optional
from urllib.parse import urlparse

MONGO_URI = os.environ.get("MONGODB_URI")
MONGO_DBNAME = os.environ.get("MONGODB_DB")  # optional override
# Optional: force TLS via env; if unset, defer to URI settings (recommended)
MONGO_TLS_ENV = os.environ.get("MONGODB_TLS")
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
        # Respect explicit MONGODB_TLS if provided, otherwise let URI decide (mongodb+srv implies TLS)
        if MONGO_TLS_ENV is not None:
            tls_flag = str(MONGO_TLS_ENV).lower() in ("1", "true", "yes", "on")
            _client = MongoClient(MONGO_URI, tls=tls_flag)
        else:
            # Do not force TLS; rely on connection string options
            _client = MongoClient(MONGO_URI)

    # Determine DB name
    db_name = MONGO_DBNAME or _extract_db_from_uri(MONGO_URI) or _default_db_name

    _db = _client[db_name]
    return _db

def close_client():
    global _client
    if _client:
        _client.close()
        _client = None


def ensure_indexes():
    """
    Create necessary indexes for MongoDB collections.
    Called during application startup.
    """
    db = get_db()
    
    # Indexes for validation_config collection
    validation_config = db.validation_config
    
    # Primary index: unique constraint on org_id + region + rule_id
    validation_config.create_index([
        ("organization_id", 1),
        ("region", 1),
        ("rule_id", 1)
    ], unique=True, sparse=False)
    
    # Index for retrieving active configs
    validation_config.create_index([
        ("organization_id", 1),
        ("enabled", 1)
    ])
    
    # Index for category-based queries
    validation_config.create_index([
        ("rule_category", 1),
        ("organization_id", 1)
    ])
    
    # Index for audit trail queries (change history)
    validation_config.create_index([
        ("updated_at", -1)
    ])


def close_client():
    global _client
    if _client:
        _client.close()
        _client = None


def get_next_invoice_id() -> int:
    """
    Atomically generate the next sequential invoice_id using MongoDB counters collection.
    
    Uses findOneAndUpdate with upsert to ensure:
    - Thread-safe / concurrency-safe
    - Idempotent initialization (creates counter doc if missing)
    - Returns monotonically increasing integers starting from 1
    
    Returns:
        int: The next invoice_id (sequential, numeric, human-readable)
    """
    db = get_db()
    
    # Use findOneAndUpdate to atomically increment counter
    # If document doesn't exist, upsert creates it with seq: 1
    counter_doc = db.counters.find_one_and_update(
        {"_id": "invoice"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True  # Return updated document
    )
    
    # Return the updated seq value
    return counter_doc.get("seq", 1)
