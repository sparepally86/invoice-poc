#!/usr/bin/env python
"""Drop validation_config MongoDB collection (Step E5 rollback)"""

import os
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "invoice-poc")

from app.storage.mongo_client import get_db

db = get_db()
try:
    db.validation_config.drop()
    print("✅ Dropped validation_config collection")
except Exception as e:
    print(f"ℹ️  Collection doesn't exist or already dropped: {e}")

# Verify
collections = db.list_collection_names()
if "validation_config" not in collections:
    print("✅ Verified: validation_config not in database")
else:
    print("❌ ERROR: validation_config still exists")
    
print(f"\nExisting collections: {', '.join(collections)}")
