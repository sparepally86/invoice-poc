# app/agents/validation_domain.py
"""
ValidationDomain: Internal abstraction that coordinates validation rule groups.

Responsibilities:
- Organize validation logic by category (structural, financial, policy, duplicate)
- Aggregate issues from all rule groups
- Compute final ValidationResult (status, summary)
- Remain deterministic and synchronous

This module is internal to ValidationAgent and should not be called directly by Orchestrator.
"""

import os
import datetime
from typing import Dict, Any, List

# tolerance in percent (e.g. 0.5 = 0.5%)
AMOUNT_TOLERANCE_PCT = float(os.environ.get("VALIDATION_AMOUNT_TOLERANCE_PCT", "0.5"))

# Soft warning threshold: issues within 2x the tolerance are warnings, beyond that are failures
AMOUNT_WARNING_THRESHOLD_PCT = float(os.environ.get("VALIDATION_AMOUNT_WARNING_THRESHOLD_PCT", "2.0"))


def _validate_structural_rules(invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate STRUCTURAL rules: Schema/format violations.
    
    STRUCTURAL rules determine whether the invoice is a coherent business document.
    All structural violations are HARD severity (blocking).
    
    Returns:
        List of structural validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    
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
    
    return issues


def _validate_financial_rules(invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate FINANCIAL rules: Internal numerical consistency.
    
    FINANCIAL rules validate amounts and consistency.
    Severity is tolerance-based: SOFT if within warning threshold, HARD if beyond.
    
    Returns:
        List of financial validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    lines = invoice_doc.get("lines", []) or []
    
    # Amount vs lines sum (robust header amount parsing)
    header_amount = header.get("total_amount")
    try:
        header_amount = float(header_amount) if header_amount is not None else 0.0
    except Exception:
        header_amount = 0.0
    
    sum_items = float(sum([float(ln.get("line_amount", 0) or 0) for ln in lines]))
    
    # Avoid division by zero
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
    
    return issues


def _validate_policy_rules(db, invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate POLICY rules: Business rule enforcement.
    
    POLICY rules enforce company and regulatory policies.
    Severity depends on the specific policy: HARD or SOFT.
    
    Returns:
        List of policy validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    
    # Vendor eligibility: Vendor must exist in master data
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
    
    return issues


def _validate_duplicate_rules(db, invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate DUPLICATE rules: Risk protection against duplicates.
    
    DUPLICATE rules protect against duplicate or risky invoices.
    Severity is usually HARD (risk protection).
    
    Returns:
        List of duplicate validation issues
    """
    issues: List[Dict[str, Any]] = []
    
    # Currently no duplicate rules implemented
    # Future: Check for same vendor + invoice number, time-window duplicates, etc.
    
    return issues


def build_validation_result(issues: List[Dict[str, Any]], validated_at: str) -> Dict[str, Any]:
    """
    Build a structured ValidationResult contract from a list of issues.
    
    Args:
        issues: List of validation issues
        validated_at: ISO timestamp of validation
    
    Returns:
        Complete ValidationResult with status, issues, summary, timestamp
    """
    hard_failures = sum(1 for issue in issues if issue.get("severity") == "HARD")
    soft_warnings = sum(1 for issue in issues if issue.get("severity") == "SOFT")
    
    # Determine status: FAIL if any HARD, WARN if any SOFT only, PASS if none
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


def validate(db, invoice_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main ValidationDomain entry point: Coordinate all validation rule groups.
    
    ValidationDomain orchestrates validation by:
    1. Running structural rules
    2. Running financial rules
    3. Running policy rules
    4. Running duplicate rules
    5. Aggregating all issues
    6. Computing final ValidationResult
    
    Args:
        db: MongoDB database connection
        invoice_doc: Invoice document to validate
    
    Returns:
        Complete ValidationResult with all issues and status
    """
    validated_at = datetime.datetime.utcnow().isoformat() + "Z"
    
    # Validate each rule category
    structural_issues = _validate_structural_rules(invoice_doc)
    financial_issues = _validate_financial_rules(invoice_doc)
    policy_issues = _validate_policy_rules(db, invoice_doc)
    duplicate_issues = _validate_duplicate_rules(db, invoice_doc)
    
    # Aggregate all issues
    all_issues = structural_issues + financial_issues + policy_issues + duplicate_issues
    
    # Build and return ValidationResult
    return build_validation_result(all_issues, validated_at)
