# app/api/dev.py
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Any, Dict, List, Optional
from app.storage.mongo_client import get_db
import uuid
import datetime
import httpx
import os
import random

router = APIRouter()

def build_invoice_from_po(
    po_doc: Dict[str, Any],
    erpsystem: str = "ecc",
    source: str = "capture",
    buyer_companycode: str = "1000",
    invoice_ref: Optional[str] = None,
    currency: str = "INR",
    split_first_line: bool = False
) -> Dict[str, Any]:
    """
    Build invoice JSON in the new format:
    {
      "header": { erpsystem, source, buyer_companycode, invoice_ref, invoice_date, vendor_number, vendor_name, currency, amount, status },
      "items": [ { buyer_companycode, amount }, ... ]
    }
    If split_first_line=True, split the first PO line into two items with buyer_companycodes "1000" & "2000"
    """
    if invoice_ref is None:
        invoice_ref = "GEN-" + uuid.uuid4().hex[:8]

    po_total = po_doc.get("total", 0)
    vendor_id = po_doc.get("vendor_id")
    vendor_name = po_doc.get("description") or vendor_id

    invoice_date = datetime.datetime.utcnow().date().isoformat()

    header = {
        "erpsystem": erpsystem,
        "source": source,
        "buyer_companycode": buyer_companycode,
        "invoice_ref": invoice_ref,
        "invoice_date": invoice_date,
        "vendor_number": vendor_id,
        "vendor_name": vendor_name,
        "currency": currency,
        "amount": po_total,
        "status": 2
    }

    items: List[Dict[str, Any]] = []

    po_lines = po_doc.get("lines", [])
    if not po_lines:
        # fallback: create single item with PO total
        items.append({"buyer_companycode": buyer_companycode, "amount": po_total})
    else:
        for idx, line in enumerate(po_lines):
            amt = line.get("amount", None)
            if amt is None:
                # compute from qty * unit_price if present
                qty = line.get("quantity", 1)
                unit = line.get("unit_price", 0)
                amt = qty * unit
            item = {"buyer_companycode": buyer_companycode, "amount": amt}
            items.append(item)

        # If splitting first line is requested, split it into two items with two company codes
        if split_first_line and len(items) >= 1:
            first_amt = items[0]["amount"]
            # naive 80/20 split to match your example (800/200)
            part1 = round(first_amt * 0.8, 2)
            part2 = round(first_amt - part1, 2)
            # replace first item
            items[0] = {"buyer_companycode": "1000", "amount": part1}
            # insert second split item right after
            items.insert(1, {"buyer_companycode": "2000", "amount": part2})

    invoice = {"header": header, "items": items}
    return invoice

@router.post("/dev/generate-invoice", response_class=JSONResponse)
async def generate_invoice(
    mode: str = Query("po"),                    # "po" or "nonpo"
    po_number: str | None = Query(None),        # optional; backend may pick random if mode=po
    split_first_line: bool | None = Query(False)
):
    """
    Dev helper:
    - mode=po -> PO-based invoice. If po_number provided, use it. Otherwise pick a random PO.
    - mode=nonpo -> generate a synthetic non-PO invoice.
    """
    db = get_db()

    try:
        if mode == "po":
            # If a po_number was provided, try to use it; otherwise pick random PO
            selected_po = None
            if po_number:
                selected_po = await db.pos.find_one({"po_number": po_number})
                if not selected_po:
                    raise HTTPException(status_code=422, detail=f"PO not found: {po_number}")
            else:
                # pick a random PO document
                po_doc = await db.pos.find_one({})
                if not po_doc:
                    raise HTTPException(status_code=422, detail="No POs found in PO master — create some POs first")
                # Use aggregation to randomly sample if many exist:
                # Note: for simplicity use a random skip approach for small datasets
                # Count total and skip random
                count = await db.pos.count_documents({})
                if count <= 1:
                    selected_po = po_doc
                else:
                    skip = random.randint(0, max(0, count - 1))
                    cursor = db.pos.find({}, limit=1, skip=skip)
                    docs = await cursor.to_list(length=1)
                    selected_po = docs[0] if docs else po_doc

            # Build invoice from selected_po
            po_doc = selected_po
            po_lines = po_doc.get("lines", []) or po_doc.get("items", []) or []
            items = []
            for ln in po_lines:
                qty = ln.get("quantity") or ln.get("qty") or 1
                amt = ln.get("amount")
                if amt is None:
                    # try unit_price * qty
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
            # Generate synthetic non-PO invoice. Pick a random vendor to attribute to.
            vendor_doc = await db.vendors.find_one({})
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
        # propagate known HTTP errors
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generator error: {str(e)}")
