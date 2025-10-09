# app/api/dev.py
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Any, Dict, List, Optional
from app.storage.mongo_client import get_db
import uuid
import datetime
import httpx
import os

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
    po_number: str,
    invoice_ref: Optional[str] = None,
    buyer_companycode: str = "1000",
    currency: str = "INR",
    split_first_line: bool = False,
    post_to_incoming: bool = Query(False, description="If true, POST the generated invoice to /api/v1/incoming"),
):
    """
    Generate an invoice JSON based on a PO.
    Query params:
      - po_number (required)
      - invoice_ref (optional)
      - buyer_companycode (defaults to 1000)
      - currency (defaults to INR)
      - split_first_line (bool) -> if true, create two items from first line with 1000/2000 split
      - post_to_incoming (bool) -> if true, POST to /api/v1/incoming (internal)
    """
    db = get_db()
    coll = db.get_collection("pos")
    po_doc = coll.find_one({"_id": po_number})
    if not po_doc:
        raise HTTPException(status_code=404, detail=f"PO not found: {po_number}")

    invoice = build_invoice_from_po(
        po_doc=po_doc,
        erpsystem="ecc",
        source="capture",
        buyer_companycode=buyer_companycode,
        invoice_ref=invoice_ref,
        currency=currency,
        split_first_line=split_first_line,
    )

    incoming_response = None
    if post_to_incoming:
        # Post to the incoming endpoint of this service
        incoming_url = os.environ.get("INTERNAL_INCOMING_URL") or "http://localhost:8000/api/v1/incoming"
        # If running in the same Render service, construct from the public host if provided:
        # You can set INTERNAL_INCOMING_URL in Render env to https://invoice-poc-1gpt.onrender.com
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post(incoming_url, json=invoice)
                incoming_response = {"status_code": r.status_code, "body": r.json() if r.status_code < 500 else r.text}
            except Exception as e:
                incoming_response = {"error": str(e)}

    return JSONResponse({"generated_invoice": invoice, "posted_to_incoming": incoming_response})
