# app/api/dev.py  (replace existing generate-invoice endpoint)
import random
import datetime
import asyncio
from fastapi import APIRouter, Query, HTTPException
from app.storage.mongo_client import get_db

router = APIRouter()

# Helper wrappers to run blocking PyMongo calls in threadpool
def _find_one_sync(coll, q):
    return coll.find_one(q)

def _count_documents_sync(coll, q):
    return coll.count_documents(q)

def _find_with_skip_sync(coll, filter_q, skip, limit=1):
    # produce a list of docs using skip/limit (blocking)
    cursor = coll.find(filter_q).skip(skip).limit(limit)
    return list(cursor)

# --- DB health check ---
@router.get("/dev/db/health")
async def dev_db_health():
    """
    Quick MongoDB connectivity check.
    Returns the result of a ping command against the configured database.
    """
    db = get_db()
    try:
        res = await asyncio.to_thread(db.command, "ping")
        return {"ok": True, "ping": res}
    except Exception as e:
        # surface error for quick diagnostics
        raise HTTPException(status_code=500, detail=f"mongo_ping_failed: {e}")

# The new endpoint
@router.post("/dev/generate-invoice")
async def generate_invoice(
    mode: str = Query("po"),                    # "po" or "nonpo"
    po_number: str | None = Query(None),        # optional; backend may pick random if mode=po
    split_first_line: bool | None = Query(False)
):
    """
    Dev helper:
    - mode=po -> PO-based invoice. If po_number provided, use it. Otherwise pick a random PO.
    - mode=nonpo -> generate a synthetic non-PO invoice.
    Uses asyncio.to_thread to call blocking PyMongo safely.
    """
    db = get_db()
    try:
        if mode == "po":
            selected_po = None
            if po_number:
                # blocking call in thread
                selected_po = await asyncio.to_thread(_find_one_sync, db.pos, {"po_number": po_number})
                if not selected_po:
                    raise HTTPException(status_code=422, detail=f"PO not found: {po_number}")
            else:
                # ensure there is at least one PO
                first_po = await asyncio.to_thread(_find_one_sync, db.pos, {})
                if not first_po:
                    raise HTTPException(status_code=422, detail="No POs found in PO master — create some POs first")

                # count docs (blocking)
                total = await asyncio.to_thread(_count_documents_sync, db.pos, {})
                if total <= 1:
                    selected_po = first_po
                else:
                    skip = random.randint(0, max(0, total - 1))
                    docs = await asyncio.to_thread(_find_with_skip_sync, db.pos, {}, skip, 1)
                    selected_po = docs[0] if docs else first_po

            po_doc = selected_po
            po_lines = po_doc.get("lines", []) or po_doc.get("items", []) or []
            items = []
            for ln in po_lines:
                qty = ln.get("quantity") or ln.get("qty") or 1
                amt = ln.get("amount")
                if amt is None:
                    amt = (ln.get("unit_price") or ln.get("price") or 0) * qty
                items.append({
                    "item_text": ln.get("item_text") or ln.get("description") or ln.get("name") or "",
                    "quantity": qty,
                    "amount": amt
                })

            total_amount = sum((it.get("amount") or 0) for it in items)
            header = {
                "po_number": po_doc.get("po_number"),
                "invoice_ref": f"GEN-{random.randint(10000,99999)}",
                "invoice_date": datetime.datetime.utcnow().date().isoformat(),
                "vendor_number": po_doc.get("vendor_id") or po_doc.get("vendor_number") or po_doc.get("vendor"),
                "vendor_name": po_doc.get("vendor_name") or po_doc.get("vendor") or "Unknown Vendor",
                "currency": po_doc.get("currency", "INR"),
                "amount": total_amount
            }

            generated = {"header": header, "items": items}
            return {"generated_invoice": generated}

        elif mode == "nonpo":
            # pick a random vendor (blocking calls run in thread)
            vendor_doc = await asyncio.to_thread(_find_one_sync, db.vendors, {})
            if not vendor_doc:
                raise HTTPException(status_code=422, detail="No vendors found in Vendor master — create some vendors first")

            num_lines = 2 if split_first_line else 1
            items = []
            for i in range(num_lines):
                qty = random.choice([1, 2, 3])
                unit_price = random.choice([1000, 2500, 5000])
                items.append({
                    "item_text": f"Synthetic line {i+1}",
                    "quantity": qty,
                    "amount": qty * unit_price
                })

            total_amount = sum(it["amount"] for it in items)
            header = {
                "invoice_ref": f"GEN-NP-{random.randint(1000,9999)}",
                "invoice_date": datetime.datetime.utcnow().date().isoformat(),
                "vendor_number": vendor_doc.get("vendor_id") or vendor_doc.get("_id"),
                "vendor_name": vendor_doc.get("name_raw") or vendor_doc.get("name") or "Vendor",
                "currency": vendor_doc.get("currency", "INR"),
                "amount": total_amount,
            }

            generated = {"header": header, "items": items}
            return {"generated_invoice": generated}

        else:
            raise HTTPException(status_code=422, detail=f"Unknown mode: {mode}")

    except HTTPException:
        raise
    except Exception as e:
        # Keep the error wrapped so frontend sees helpful message
        raise HTTPException(status_code=500, detail=f"Generator error: {str(e)}")
