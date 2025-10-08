# app/storage/mongo_client.py
from pymongo import MongoClient
import os
from typing import Optional

MONGO_URI = os.environ.get("MONGODB_URI")

_client: Optional[MongoClient] = None
_db = None

def get_db():
    global _client, _db
    if _db:
        return _db
    if not MONGO_URI:
        raise RuntimeError("MONGODB_URI not set")
    _client = MongoClient(MONGO_URI, tls=True)
    # if the URI included a database after the slash, get_default_database() may work:
    _db = _client.get_default_database() or _client["invoice_poc"]
    return _db

def close_client():
    global _client
    if _client:
        _client.close()
        _client = None
