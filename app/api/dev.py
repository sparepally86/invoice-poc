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
async def generate_invoice(po_number: str | None = Query(None), split_first_line: bool | None = Query(False)):
    """
    Dev helper: generate a synthetic invoice.
    - If po_number is provided, build invoice from that PO (existing behavior).
    - If po_number is not provided, create a non-PO invoice using an existing vendor (random) or a fallback.
    """

    db = get_db()

    try:
        if po_number:
            # existing PO-based flow: try to fetch the PO and its vendor
            po_doc = await db.pos.find_one({"po_number": po_number})
            if not po_doc:
                # Return a clear error (but 422 was previous behaviour) — choose 404 or 422 as you prefer
                raise HTTPException(status_code=422, detail=f"PO not found: {po_number}")

            # get vendor if present on PO
            vendor_id = po_doc.get("vendor_id") or po_doc.get("vendor_number")
            vendor = None
            if vendor_id:
                vendor = await db.vendors.find_one({"vendor_id": vendor_id}) or await db.vendors.find_one({"_id": vendor_id})

            # build invoice header and items based on PO
            items = []
            po_lines = po_doc.get("lines", [])
            for ln in po_lines:
                items.append({
                    "item_text": ln.get("item_text") or ln.get("description") or ln.get("name"),
                    "quantity": ln.get("quantity") or ln.get("qty") or 1,
                    "amount": ln.get("amount") or (ln.get("unit_price") or 0) * (ln.get("quantity") or 1),
                })

            total_amount = sum((it.get("amount") or 0) for it in items)

            header = {
                "po_number": po_number,
                "invoice_ref": f"GEN-{random.randint(10000,99999)}",
                "invoice_date": datetime.datetime.utcnow().date().isoformat(),
                "vendor_number": vendor.get("vendor_id") if vendor else (po_doc.get("vendor_id") or "UNKNOWN"),
                "vendor_name": vendor.get("name_raw") if vendor else po_doc.get("vendor_name", "Unknown Vendor"),
                "currency": po_doc.get("currency", "INR"),
                "amount": total_amount
            }

            generated = {"header": header, "items": items}
            return {"generated_invoice": generated}

        else:
            # Non-PO flow: pick a random vendor or fallback to first vendor
            vendor = await db.vendors.find_one({})
            if not vendor:
                # If no vendors exist in DB, return a useful 422 with message
                raise HTTPException(status_code=422, detail="No vendors found in Vendor master — create some vendors first")

            # Create a simple invoice with 1-2 lines
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
                "vendor_number": vendor.get("vendor_id") or vendor.get("_id"),
                "vendor_name": vendor.get("name_raw") or vendor.get("name") or "Vendor",
                "currency": vendor.get("currency", "INR"),
                "amount": total_amount,
            }

            generated = {"header": header, "items": items}
            return {"generated_invoice": generated}

    except HTTPException:
        raise
    except Exception as e:
        # Unexpected error -> helpful 500
        raise HTTPException(status_code=500, detail=f"Generator error: {str(e)}")
