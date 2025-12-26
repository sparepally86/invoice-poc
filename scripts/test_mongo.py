from app.storage.mongo_client import get_db
import traceback

try:
    db = get_db()
    print('DB OK, db name:', db.name)
    print('Collections:', db.list_collection_names())
except Exception:
    traceback.print_exc()
