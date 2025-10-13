# app/agents/validation.py
import os
import datetime
from typing import Dict, Any, List
from app.agents._common import ensure_agent_response

# tolerance in percent (e.g. 0.5 = 0.5%)
AMOUNT_TOLERANCE_PCT = float(os.environ.get("VALIDATION_AMOUNT_TOLERANCE_PCT", "0.5"))

def run_validation(db, invoice_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic validation rules.
    Returns an AgentResponse-like dict.
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    items = invoice_doc.get("items", []) or []

    # Mandatory fields
    mandatory = ["invoice_ref", "invoice_date", "vendor_number", "currency", "amount"]
    for f in mandatory:
        if f not in header or header.get(f) in (None, ""):
            issues.append({
                "code": "MISSING_FIELD",
                "field": f"header.{f}",
                "severity": "E",
                "message": f"{f} is missing"
            })

    # Vendor exists?
    vendor_id = header.get("vendor_number")
    vendor_ok = False
    if vendor_id:
        # vendors collection uses _id = vendor_id in our POC
        v = db.get_collection("vendors").find_one({"_id": vendor_id})
        if v:
            vendor_ok = True
        else:
            # try fallback search
            v2 = db.get_collection("vendors").find_one({"vendor_id": vendor_id})
            if v2:
                vendor_ok = True
    if not vendor_ok:
        issues.append({
            "code": "VENDOR_NOT_FOUND",
            "field": "header.vendor_number",
            "severity": "E",
            "message": f"Vendor '{vendor_id}' not found in vendor master"
        })

    # Amount vs items sum (robust header amount parsing)
    header_amount = header.get("amount")
    if header_amount is None:
        gt = header.get("grand_total")
        if isinstance(gt, dict):
            header_amount = gt.get("value")
        else:
            header_amount = gt
    try:
        header_amount = float(header_amount) if header_amount is not None else 0.0
    except Exception:
        header_amount = 0.0
    sum_items = float(sum([float(i.get("amount", 0) or 0) for i in items]))
    # avoid division by zero
    diff_pct = 0.0
    if header_amount:
        diff_pct = abs(sum_items - float(header_amount)) / float(header_amount) * 100.0
    else:
        if sum_items != 0:
            diff_pct = 100.0

    if diff_pct > AMOUNT_TOLERANCE_PCT:
        issues.append({
            "code": "AMOUNT_MISMATCH",
            "field": "header.amount",
            "severity": "E",
            "message": f"Header amount {header_amount} != sum(items) {sum_items} (diff_pct={diff_pct:.2f} > tol={AMOUNT_TOLERANCE_PCT})"
        })

    # Determine status
    has_error = any(i.get("severity") == "E" for i in issues)
    status = "completed" if not has_error else "needs_human"

    result = {
        "valid": not has_error,
        "issues": issues,
        "field_confidences": {},   # placeholder for later
        "suggestions": {}
    }

    agent_output = {
        "agent": "ValidationAgent",
        "invoice_id": invoice_doc.get("_id") or invoice_doc.get("invoice_id"),
        "status": status,
        "result": result,
        "next_agent": "POMatchingAgent" if not has_error else None,
        "score": max(0.0, 1.0 - min(1.0, len(issues) / 10.0)),
        "errors": [],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

    return ensure_agent_response("ValidationAgent", agent_output)