# app/utils/pii_redaction.py
"""
Comprehensive PII redaction utility for AP automation.

Redacts sensitive information BEFORE sending text to LLM:
- Vendor identifiers (vendor names, numbers)
- Financial identifiers (bank accounts, IFSC codes)
- Tax identifiers (GST, PAN, VAT)
- Contact details (email, phone)

Behavior:
- Conservative, rule-based patterns
- Deterministic redaction (same input → same output)
- Preserves sentence structure
- Fail-safe: returns original text if redaction fails
"""

import re
import logging
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# =====================
# Regex Patterns (Strict)
# =====================

# TAX & FINANCIAL IDENTIFIERS
# GST: 2-digit state code + 5 char PAN format + 4 digits + Z + 1 char
_GST_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}\b")

# PAN: 10 characters - 5 letters, 4 digits, 1 letter (India)
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")

# VAT ID patterns (EU format)
_VAT_RE = re.compile(r"\b[A-Z]{2}\d{8,12}\b")

# Bank account numbers (9-18 digits)
_BANK_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")

# IFSC code (India: 4 letters + 0 + 6 chars)
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

# CONTACT DETAILS
# Email: standard pattern
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Phone: More flexible pattern to catch various formats
# Matches: +1-212-555-0173, (555) 123-4567, 555-123-4567, +91-9876-543-210, etc.
_PHONE_RE = re.compile(r"\+?\d{1,3}[-.\s]?\(?[0-9]{2,4}\)?[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,6}(?!\d)")

# CREDIT CARD (Luhn-like: 13-19 digits with optional separators)
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[-\s]*?){13,19}\b")

# =====================
# PII Extraction Functions
# =====================

def _extract_vendor_identifiers(invoice: Dict[str, Any]) -> Set[str]:
    """
    Extract vendor names and numbers from invoice for targeted redaction.
    Returns set of vendor identifiers to redact.
    """
    vendors = set()
    
    header = invoice.get("header", {}) or {}
    
    # Vendor name
    vendor_name = header.get("vendor") or header.get("vendor_name") or header.get("supplier")
    if vendor_name and isinstance(vendor_name, str) and len(vendor_name) > 0:
        vendors.add(vendor_name)
    
    # Vendor number
    vendor_num = header.get("vendor_number") or header.get("vendor_id") or header.get("supplier_id")
    if vendor_num:
        vendors.add(str(vendor_num))
    
    # Vendor in top-level invoice object
    vendor_obj = invoice.get("vendor", {}) or {}
    if isinstance(vendor_obj, dict):
        vname = vendor_obj.get("name") or vendor_obj.get("vendor_name")
        if vname:
            vendors.add(vname)
        vid = vendor_obj.get("vendor_id") or vendor_obj.get("id")
        if vid:
            vendors.add(str(vid))
    
    return vendors


def _redact_vendor_identifiers(text: str, vendors: Set[str]) -> str:
    """
    Redact specific vendor names and numbers from text.
    Uses flexible matching to handle special characters and word boundaries.
    """
    if not text or not vendors:
        return text
    
    result = text
    for vendor in vendors:
        if not vendor or len(vendor) < 2:
            continue
        # Escape special regex characters in vendor name
        escaped = re.escape(vendor)
        # Try word boundary first for clean matches
        pattern1 = rf"\b{escaped}\b"
        # Try without strict word boundaries for special characters
        pattern2 = rf"(?:^|\s){escaped}(?:$|\s|\.|,)"
        
        try:
            # Try word boundary first
            new_result = re.sub(pattern1, "[REDACTED_VENDOR]", result, flags=re.IGNORECASE)
            if new_result != result:
                result = new_result
            else:
                # If no match with word boundary, try more flexible pattern
                result = re.sub(pattern2, lambda m: m.group(0).replace(vendor, "[REDACTED_VENDOR]", flags=re.IGNORECASE), result)
        except Exception:
            # Fallback: plain string replacement if regex fails
            result = result.replace(vendor, "[REDACTED_VENDOR]")
    
    return result


def _redact_pattern(text: str, pattern: re.Pattern, replacement: str) -> str:
    """
    Helper to safely redact text using regex pattern.
    Returns original text if redaction fails.
    """
    if not text:
        return text
    try:
        return pattern.sub(replacement, text)
    except Exception:
        logger.debug(f"Pattern redaction failed for {replacement}, keeping original text")
        return text


def redact_pii(text: str, invoice: Optional[Dict[str, Any]] = None) -> str:
    """
    Main PII redaction function. Redacts all PII categories from text.
    
    Args:
        text: The text to redact (typically a prompt for LLM)
        invoice: Optional invoice object to extract vendor identifiers
    
    Returns:
        Redacted text with PII replaced by [REDACTED_*] placeholders
    """
    if not text:
        return text
    
    result = str(text)
    
    try:
        # 1) TAX IDENTIFIERS
        result = _redact_pattern(result, _GST_RE, "[REDACTED_GST]")
        result = _redact_pattern(result, _PAN_RE, "[REDACTED_PAN]")
        result = _redact_pattern(result, _VAT_RE, "[REDACTED_VAT]")
        
        # 2) FINANCIAL IDENTIFIERS
        result = _redact_pattern(result, _IFSC_RE, "[REDACTED_IFSC]")
        result = _redact_pattern(result, _CREDIT_CARD_RE, "[REDACTED_CC]")
        
        # Bank accounts last (most permissive - can overlap with other patterns)
        # Only redact if >9 consecutive digits
        result = _redact_pattern(result, _BANK_ACCOUNT_RE, "[REDACTED_BANK]")
        
        # 3) CONTACT DETAILS
        result = _redact_pattern(result, _EMAIL_RE, "[REDACTED_EMAIL]")
        result = _redact_pattern(result, _PHONE_RE, "[REDACTED_PHONE]")
        
        # 4) VENDOR IDENTIFIERS (targeted, from invoice if available)
        if invoice:
            vendors = _extract_vendor_identifiers(invoice)
            result = _redact_vendor_identifiers(result, vendors)
        
        return result
    
    except Exception as e:
        logger.exception(f"PII redaction failed: {e}. Returning original text as fallback.")
        return text


def get_redaction_stats(original: str, redacted: str) -> Dict[str, int]:
    """
    Analyze redaction to count different PII types removed.
    Returns dict with counts of each redaction type.
    """
    stats = {}
    
    patterns = {
        "gst": _GST_RE,
        "pan": _PAN_RE,
        "vat": _VAT_RE,
        "ifsc": _IFSC_RE,
        "credit_card": _CREDIT_CARD_RE,
        "bank_account": _BANK_ACCOUNT_RE,
        "email": _EMAIL_RE,
        "phone": _PHONE_RE,
    }
    
    replacements = {
        "gst": "[REDACTED_GST]",
        "pan": "[REDACTED_PAN]",
        "vat": "[REDACTED_VAT]",
        "ifsc": "[REDACTED_IFSC]",
        "credit_card": "[REDACTED_CC]",
        "bank_account": "[REDACTED_BANK]",
        "email": "[REDACTED_EMAIL]",
        "phone": "[REDACTED_PHONE]",
    }
    
    for pii_type, pattern in patterns.items():
        try:
            matches = len(pattern.findall(original))
            replacements_made = redacted.count(replacements[pii_type])
            stats[pii_type] = replacements_made
        except Exception:
            stats[pii_type] = 0
    
    return stats
