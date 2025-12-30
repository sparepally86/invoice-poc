# app/agents/validation.py
import os
import datetime
from typing import Dict, Any, List
from app.agents._common import ensure_agent_response

# tolerance in percent (e.g. 0.5 = 0.5%)
# Amount mismatches within this tolerance are SOFT warnings
AMOUNT_TOLERANCE_PCT = float(os.environ.get("VALIDATION_AMOUNT_TOLERANCE_PCT", "0.5"))

# Soft warning threshold: issues within 2x the tolerance are warnings, beyond that are failures
AMOUNT_WARNING_THRESHOLD_PCT = float(os.environ.get("VALIDATION_AMOUNT_WARNING_THRESHOLD_PCT", "2.0"))


def _build_validation_result(issues: List[Dict[str, Any]], validated_at: str) -> Dict[str, Any]:
    """
    Build a structured ValidationResult contract from a list of issues.
    
    Returns:
        {
            "status": "PASS" | "WARN" | "FAIL",
            "issues": [...],
            "summary": {"hard_failures": int, "soft_warnings": int},
            "validated_at": "<ISO timestamp>"
        }
    """
    hard_failures = sum(1 for issue in issues if issue.get("severity") == "HARD")
    soft_warnings = sum(1 for issue in issues if issue.get("severity") == "SOFT")
    
    # Determine status
    if hard_failures > 0:
        status = "FAIL"
    elif soft_warnings > 0:
        status = "WARN"
    else:
        status = "PASS"
    
    return {
        "status": status,
        "issues": issues,
        "summary": {
            "hard_failures": hard_failures,
            "soft_warnings": soft_warnings
        },
        "validated_at": validated_at
    }


def run_validation(db, invoice_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic validation rules.
    Returns an AgentResponse-like dict with structured ValidationResult.
    Validates against canonical schema v1: invoice_number, invoice_date, vendor_name, vendor_number, currency, total_amount
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    lines = invoice_doc.get("lines", []) or []
    validated_at = datetime.datetime.utcnow().isoformat() + "Z"

    # Mandatory fields per canonical schema v1
    mandatory = ["invoice_number", "invoice_date", "vendor_number", "currency", "total_amount"]
    for f in mandatory:
        if f not in header or header.get(f) in (None, ""):
            issues.append({
                "code": "MISSING_FIELD",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": f"header.{f}",
                "message": f"{f} is missing",
                "metadata": {}
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
            "category": "POLICY",
            "severity": "HARD",
            "field": "header.vendor_number",
            "message": f"Vendor '{vendor_id}' not found in vendor master",
            "metadata": {}
        })

    # Amount vs lines sum (robust header amount parsing)
    # FINANCIAL validation: internal numerical consistency
    # Severity: SOFT if within warning threshold, HARD if beyond
    header_amount = header.get("total_amount")
    try:
        header_amount = float(header_amount) if header_amount is not None else 0.0
    except Exception:
        header_amount = 0.0
    sum_items = float(sum([float(ln.get("line_amount", 0) or 0) for ln in lines]))
    # avoid division by zero
    diff_pct = 0.0
    if header_amount:
        diff_pct = abs(sum_items - float(header_amount)) / float(header_amount) * 100.0
    else:
        if sum_items != 0:
            diff_pct = 100.0

    # Check for amount mismatch and determine severity based on tolerance
    if diff_pct > AMOUNT_TOLERANCE_PCT:
        # Determine severity: SOFT if within warning threshold, HARD if beyond
        severity = "SOFT" if diff_pct <= AMOUNT_WARNING_THRESHOLD_PCT else "HARD"
        issues.append({
            "code": "AMOUNT_MISMATCH",
            "category": "FINANCIAL",
            "severity": severity,
            "field": "header.total_amount",
            "message": f"Header total_amount {header_amount} != sum(lines) {sum_items} (diff_pct={diff_pct:.2f})",
            "metadata": {
                "header_amount": header_amount,
                "sum_items": sum_items,
                "diff_pct": round(diff_pct, 2),
                "tolerance_pct": AMOUNT_TOLERANCE_PCT,
                "warning_threshold_pct": AMOUNT_WARNING_THRESHOLD_PCT
            }
        })

    # Build structured ValidationResult
    validation_result = _build_validation_result(issues, validated_at)
    
    # Maintain backward compatibility: determine if validation passed
    has_hard_failures = validation_result["summary"]["hard_failures"] > 0
    agent_status = "completed" if not has_hard_failures else "needs_human"

    # For backward compatibility with orchestrator, also include old-style result
    result = {
        "valid": not has_hard_failures,
        "issues": issues,
        "field_confidences": {},   # placeholder for later
        "suggestions": {}
    }

    agent_output = {
        "agent": "ValidationAgent",
        "invoice_id": invoice_doc.get("_id") or invoice_doc.get("invoice_id"),
        "status": agent_status,
        "result": result,
        "validation": validation_result,  # NEW: structured ValidationResult
        "next_agent": "POMatchingAgent" if not has_hard_failures else None,
        "score": max(0.0, 1.0 - min(1.0, len(issues) / 10.0)),
        "errors": [],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

    return ensure_agent_response("ValidationAgent", agent_output)