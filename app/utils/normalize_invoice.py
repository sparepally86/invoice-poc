from typing import Dict

def ensure_minimal_structure(invoice: Dict) -> Dict:
    """
    Ensure invoice has both 'lines' and 'items' referencing the same list,
    and also populate header.amount from grand_total.value if missing.
    Call early during ingestion and before agents run.
    """
    if invoice is None:
        return invoice

    # Prefer 'lines' as canonical; if only 'items' exists, copy it to 'lines'
    lines = invoice.get("lines")
    items = invoice.get("items")

    if lines is None and items is not None:
        invoice["lines"] = items
    elif items is None and lines is not None:
        invoice["items"] = lines
    elif items is None and lines is None:
        invoice["lines"] = []
        invoice["items"] = []

    # Normalize header.amount for backward compatibility
    header = invoice.get("header") or {}
    if "amount" not in header or header.get("amount") is None:
        gt = header.get("grand_total") or {}
        if isinstance(gt, dict) and "value" in gt:
            header["amount"] = gt.get("value")
        elif isinstance(header.get("grand_total"), (int, float)):
            header["amount"] = header.get("grand_total")
    invoice["header"] = header

    return invoice
