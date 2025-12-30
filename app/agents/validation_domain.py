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
    
    Includes:
    - E1-S1: Empty or meaningless line description
    - E1-S2: Duplicate or invalid line numbers
    - E1-S3: Header total with no lines
    - E1-S4: Zero or negative quantity (non-credit invoice)
    
    Returns:
        List of structural validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    lines = invoice_doc.get("lines", []) or []
    
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
    
    # === E1-S1: Empty or Meaningless Line Description ===
    # Each invoice line must have a non-empty, non-whitespace description
    for idx, line in enumerate(lines):
        description = line.get("description", "")
        if isinstance(description, str):
            description = description.strip()
        if not description:
            issues.append({
                "code": "LINE_DESCRIPTION_EMPTY",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": "lines[].description",
                "message": "Invoice line description cannot be empty",
                "metadata": {"line_index": idx}
            })
    
    # === E1-S2: Duplicate or Invalid Line Numbers ===
    # Line numbers must be positive integers and unique across the invoice
    line_numbers_seen = set()
    for idx, line in enumerate(lines):
        line_number = line.get("line_number")
        
        # Check if line_number is valid (positive integer)
        try:
            line_num_int = int(line_number) if line_number is not None else None
            if line_num_int is None or line_num_int <= 0:
                issues.append({
                    "code": "INVALID_LINE_NUMBER",
                    "category": "STRUCTURAL",
                    "severity": "HARD",
                    "field": "lines[].line_number",
                    "message": "Invoice line numbers must be unique positive integers",
                    "metadata": {"line_index": idx, "line_number": line_number}
                })
            elif line_num_int in line_numbers_seen:
                # Duplicate line number
                issues.append({
                    "code": "INVALID_LINE_NUMBER",
                    "category": "STRUCTURAL",
                    "severity": "HARD",
                    "field": "lines[].line_number",
                    "message": "Invoice line numbers must be unique positive integers",
                    "metadata": {"line_index": idx, "line_number": line_num_int, "reason": "duplicate"}
                })
            else:
                line_numbers_seen.add(line_num_int)
        except (ValueError, TypeError):
            # Non-numeric line number
            issues.append({
                "code": "INVALID_LINE_NUMBER",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": "lines[].line_number",
                "message": "Invoice line numbers must be unique positive integers",
                "metadata": {"line_index": idx, "line_number": line_number, "reason": "non-numeric"}
            })
    
    # === E1-S3: Header Total with No Lines ===
    # If header.total_amount > 0, invoice must contain at least one line
    total_amount = header.get("total_amount")
    try:
        total_amount = float(total_amount) if total_amount is not None else 0.0
    except Exception:
        total_amount = 0.0
    
    if total_amount > 0 and (not lines or len(lines) == 0):
        issues.append({
            "code": "TOTAL_WITHOUT_LINES",
            "category": "STRUCTURAL",
            "severity": "HARD",
            "field": "header.total_amount",
            "message": "Invoice total cannot exist without invoice lines",
            "metadata": {"total_amount": total_amount, "lines_count": len(lines)}
        })
    
    # === E1-S4: Zero or Negative Quantity (Non-Credit Invoice) ===
    # Invoice line quantity must be > 0 for standard invoices
    for idx, line in enumerate(lines):
        quantity = line.get("quantity")
        try:
            quantity_num = float(quantity) if quantity is not None else 0.0
            if quantity_num <= 0:
                issues.append({
                    "code": "INVALID_LINE_QUANTITY",
                    "category": "STRUCTURAL",
                    "severity": "HARD",
                    "field": "lines[].quantity",
                    "message": "Invoice line quantity must be greater than zero",
                    "metadata": {"line_index": idx, "quantity": quantity_num}
                })
        except (ValueError, TypeError):
            # Invalid quantity value
            issues.append({
                "code": "INVALID_LINE_QUANTITY",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": "lines[].quantity",
                "message": "Invoice line quantity must be greater than zero",
                "metadata": {"line_index": idx, "quantity": quantity, "reason": "non-numeric"}
            })
    
    return issues


def _validate_financial_rules(invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate FINANCIAL rules: Internal numerical consistency.
    
    FINANCIAL rules validate amounts and consistency.
    Includes:
    - E2-F1: Header total vs line sum mismatch (tolerance-based, $1.00 fixed)
    - E2-F2: Tax total consistency (tolerance-based, $1.00 fixed)
    - E2-F3: Discount math validation (always SOFT)
    - E2-F4: Credit memo sign validation (always HARD)
    
    Returns:
        List of financial validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    lines = invoice_doc.get("lines", []) or []
    
    # Fixed tolerance for E2 rules: $1.00 absolute difference
    ABSOLUTE_TOLERANCE = 1.00
    
    # === E2-F1: Header Total vs Line Sum Mismatch ===
    # Header total must equal sum of line amounts within $1.00 tolerance
    header_amount = header.get("total_amount")
    try:
        header_amount = float(header_amount) if header_amount is not None else 0.0
    except Exception:
        header_amount = 0.0
    
    sum_items = float(sum([float(ln.get("line_amount", 0) or 0) for ln in lines]))
    
    # Calculate absolute difference
    diff_abs = abs(sum_items - float(header_amount))
    
    if diff_abs > ABSOLUTE_TOLERANCE:
        # Absolute difference exceeds tolerance
        severity = "HARD"
        message = "Invoice total does not match sum of line amounts"
    elif diff_abs > 0:
        # Small difference within tolerance
        severity = "SOFT"
        message = "Invoice total slightly differs from sum of line amounts"
    else:
        # No difference
        severity = None
    
    if severity:
        issues.append({
            "code": "TOTAL_LINE_MISMATCH",
            "category": "FINANCIAL",
            "severity": severity,
            "field": "header.total_amount",
            "message": message,
            "metadata": {
                "header_total": header_amount,
                "line_sum": sum_items,
                "diff_abs": round(diff_abs, 2),
                "tolerance": ABSOLUTE_TOLERANCE
            }
        })
    
    # === E2-F2: Tax Total Consistency ===
    # Header tax total must equal sum of tax amounts across lines (if tax is present)
    header_tax = header.get("tax_amount")
    if header_tax is not None:
        try:
            header_tax = float(header_tax)
        except Exception:
            header_tax = 0.0
    else:
        header_tax = 0.0
    
    # Sum tax amounts from lines (only if tax_amount field exists)
    sum_tax = 0.0
    has_tax = False
    for ln in lines:
        if "tax_amount" in ln:
            has_tax = True
            try:
                tax_val = float(ln.get("tax_amount", 0) or 0)
                sum_tax += tax_val
            except Exception:
                pass
    
    # Only check if tax is present
    if has_tax or header_tax != 0.0:
        diff_tax_abs = abs(sum_tax - header_tax)
        
        if diff_tax_abs > ABSOLUTE_TOLERANCE:
            severity = "HARD"
            message = "Invoice tax total does not match sum of line taxes"
        elif diff_tax_abs > 0:
            severity = "SOFT"
            message = "Invoice tax total slightly differs from sum of line taxes"
        else:
            severity = None
        
        if severity:
            issues.append({
                "code": "TAX_TOTAL_MISMATCH",
                "category": "FINANCIAL",
                "severity": severity,
                "field": "header.tax_amount",
                "message": message,
                "metadata": {
                    "header_tax": header_tax,
                    "line_tax_sum": sum_tax,
                    "diff_abs": round(diff_tax_abs, 2),
                    "tolerance": ABSOLUTE_TOLERANCE
                }
            })
    
    # === E2-F3: Discount Math Validation ===
    # If discount rate or amount is present, discount amount must match base × rate
    discount_amount = header.get("discount_amount")
    discount_rate = header.get("discount_rate")
    
    if discount_amount is not None or discount_rate is not None:
        try:
            discount_amount = float(discount_amount) if discount_amount is not None else 0.0
            discount_rate = float(discount_rate) if discount_rate is not None else 0.0
        except Exception:
            discount_amount = 0.0
            discount_rate = 0.0
        
        # If both are present, validate math
        if discount_amount > 0 and discount_rate > 0:
            # For simplicity, check if discount_amount ≈ subtotal × (discount_rate / 100)
            # subtotal = header_amount (before discount)
            if header_amount > 0:
                expected_discount = header_amount * (discount_rate / 100.0)
                discount_diff = abs(expected_discount - discount_amount)
                
                if discount_diff > ABSOLUTE_TOLERANCE:
                    issues.append({
                        "code": "DISCOUNT_MATH_MISMATCH",
                        "category": "FINANCIAL",
                        "severity": "SOFT",
                        "field": "header.discount",
                        "message": "Discount amount does not match calculated value",
                        "metadata": {
                            "discount_amount": discount_amount,
                            "discount_rate": discount_rate,
                            "expected_discount": round(expected_discount, 2),
                            "diff": round(discount_diff, 2)
                        }
                    })
    
    # === E2-F4: Credit Memo Sign Validation ===
    # If invoice is marked as credit memo, header total and line amounts must be negative
    is_credit_memo = header.get("is_credit_memo") or header.get("invoice_type") == "credit_memo"
    
    if is_credit_memo:
        # Check if header total is negative
        if header_amount >= 0:
            issues.append({
                "code": "INVALID_CREDIT_MEMO_SIGN",
                "category": "FINANCIAL",
                "severity": "HARD",
                "field": "header.total_amount",
                "message": "Credit memo amounts must be negative",
                "metadata": {
                    "total_amount": header_amount,
                    "reason": "Credit memo total must be negative"
                }
            })
        
        # Check if line amounts are negative
        for idx, line in enumerate(lines):
            line_amount = line.get("line_amount")
            try:
                line_amount = float(line_amount) if line_amount is not None else 0.0
            except Exception:
                line_amount = 0.0
            
            if line_amount >= 0:
                issues.append({
                    "code": "INVALID_CREDIT_MEMO_SIGN",
                    "category": "FINANCIAL",
                    "severity": "HARD",
                    "field": "lines[].line_amount",
                    "message": "Credit memo amounts must be negative",
                    "metadata": {
                        "line_index": idx,
                        "line_amount": line_amount,
                        "reason": "All credit memo line amounts must be negative"
                    }
                })
    
    return issues


def _validate_policy_rules(db, invoice_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate POLICY rules: Business rule enforcement.
    
    POLICY rules enforce company and regulatory policies.
    Severity depends on the specific policy: HARD or SOFT.
    
    Includes:
    - Vendor eligibility (existing)
    - E3-P1: Allowed currency validation
    - E3-P2: Invoice date window validation
    - E3-P3: High amount threshold warning
    - E3-P4: Country-specific mandatory fields
    
    Returns:
        List of policy validation issues
    """
    issues: List[Dict[str, Any]] = []
    header = invoice_doc.get("header", {})
    lines = invoice_doc.get("lines", []) or []
    
    # ==================== EXISTING RULE ====================
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
    
    # ==================== E3-P1: Allowed Currency Validation ====================
    # Define allowed currencies (non-configurable in Step E3)
    allowed_currencies = ["INR", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]
    
    currency = header.get("currency")
    if currency and currency not in allowed_currencies:
        issues.append({
            "code": "UNSUPPORTED_CURRENCY",
            "category": "POLICY",
            "severity": "HARD",
            "field": "header.currency",
            "message": f"Invoice currency '{currency}' is not supported",
            "metadata": {
                "currency": currency,
                "allowed_currencies": allowed_currencies
            }
        })
    
    # ==================== E3-P2: Invoice Date Window Validation ====================
    invoice_date_str = header.get("invoice_date")
    if invoice_date_str:
        try:
            # Parse ISO format date string
            if isinstance(invoice_date_str, str):
                # Try ISO format first
                if "T" in invoice_date_str:
                    invoice_date = datetime.datetime.fromisoformat(invoice_date_str.replace("Z", "+00:00")).date()
                else:
                    invoice_date = datetime.datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
            else:
                invoice_date = invoice_date_str  # already a date object
            
            today = datetime.datetime.utcnow().date()
            
            # Check for future date (HARD)
            if invoice_date > today:
                issues.append({
                    "code": "INVALID_INVOICE_DATE",
                    "category": "POLICY",
                    "severity": "HARD",
                    "field": "header.invoice_date",
                    "message": "Invoice date cannot be in the future",
                    "metadata": {
                        "invoice_date": str(invoice_date),
                        "today": str(today),
                        "days_in_future": (invoice_date - today).days
                    }
                })
            else:
                # Check if older than 180 days (SOFT)
                days_old = (today - invoice_date).days
                if days_old > 180:
                    issues.append({
                        "code": "INVALID_INVOICE_DATE",
                        "category": "POLICY",
                        "severity": "SOFT",
                        "field": "header.invoice_date",
                        "message": "Invoice date is older than allowed window (180 days)",
                        "metadata": {
                            "invoice_date": str(invoice_date),
                            "today": str(today),
                            "days_old": days_old,
                            "max_allowed_days": 180
                        }
                    })
        except (ValueError, TypeError) as e:
            # Could not parse date - emit structural issue, not policy
            # (this should be caught by structural rules)
            pass
    
    # ==================== E3-P3: High Amount Threshold Warning ====================
    # High-value invoices require additional attention (SOFT/WARN only)
    high_amount_threshold = 1_000_000  # Non-configurable in Step E3
    
    total_amount = header.get("total_amount")
    if total_amount:
        try:
            amount_val = float(total_amount)
            if amount_val > high_amount_threshold:
                issues.append({
                    "code": "HIGH_VALUE_INVOICE",
                    "category": "POLICY",
                    "severity": "SOFT",
                    "field": "header.total_amount",
                    "message": "Invoice amount exceeds standard review threshold",
                    "metadata": {
                        "total_amount": amount_val,
                        "threshold": high_amount_threshold,
                        "exceeds_by": amount_val - high_amount_threshold
                    }
                })
        except (ValueError, TypeError):
            pass
    
    # ==================== E3-P4: Country-Specific Mandatory Fields ====================
    country = header.get("country")
    if country:
        if country == "IN":
            # India: GSTIN required
            gstin = header.get("gstin")
            if not gstin or gstin == "":
                issues.append({
                    "code": "MISSING_COUNTRY_MANDATORY_FIELD",
                    "category": "POLICY",
                    "severity": "HARD",
                    "field": "header.country",
                    "message": "Mandatory GSTIN field missing for India invoices",
                    "metadata": {
                        "country": country,
                        "required_field": "gstin"
                    }
                })
        elif country == "US":
            # US: Tax ID required
            tax_id = header.get("tax_id")
            if not tax_id or tax_id == "":
                issues.append({
                    "code": "MISSING_COUNTRY_MANDATORY_FIELD",
                    "category": "POLICY",
                    "severity": "HARD",
                    "field": "header.country",
                    "message": "Mandatory Tax ID field missing for US invoices",
                    "metadata": {
                        "country": country,
                        "required_field": "tax_id"
                    }
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
