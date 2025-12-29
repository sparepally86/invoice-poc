"""
Canonical invoice schema validation utility.

Validates invoices against the canonical schema v1, with status-aware rules:
- DRAFT: Minimal validation (identity, source, status, audit only)
- RECEIVED: Full validation (document, header, lines required + all fields checked)

Note: Transforms MongoDB documents for schema compliance:
- Normalizes vendor data if present (not in schema)
- Normalizes _workflow field (not in schema, stored separately)
- Removes MongoDB internal fields (_id)
"""

import json
from pathlib import Path
from typing import Tuple, List
from jsonschema import Draft7Validator, FormatChecker


# Load schema once at module import time
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "invoice" / "invoice.schema.v1.json"
_SCHEMA = None
_VALIDATOR = None


def _load_schema() -> dict:
    """Load canonical invoice schema from disk."""
    global _SCHEMA
    if _SCHEMA is None:
        with open(_SCHEMA_PATH, 'r', encoding='utf-8') as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


def get_validator() -> Draft7Validator:
    """Get or create the Draft7Validator instance."""
    global _VALIDATOR
    if _VALIDATOR is None:
        schema = _load_schema()
        _VALIDATOR = Draft7Validator(schema, format_checker=FormatChecker())
    return _VALIDATOR


def _normalize_for_schema(invoice_doc: dict) -> dict:
    """
    Normalize a MongoDB invoice document for schema validation.
    
    Transforms the API's flat structure into canonical schema structure:
    - Creates identity object with invoice_id, tenant_id, trace_id
    - Creates audit object with created_at, updated_at
    - Keeps source, document, header, lines as-is
    - Removes application-specific fields (_id, vendor, _workflow)
    
    Args:
        invoice_doc: Raw MongoDB invoice document
        
    Returns:
        Normalized document suitable for schema validation
    """
    # Create a clean document for schema validation
    doc = {}
    
    # Map required identity fields
    if "identity" not in invoice_doc:
        # Build from flat structure if needed
        doc["identity"] = {
            "invoice_id": invoice_doc.get("invoice_id"),
            "tenant_id": invoice_doc.get("tenant_id") or "default-tenant",
            "trace_id": invoice_doc.get("trace_id") or ""
        }
    else:
        doc["identity"] = invoice_doc["identity"]
    
    # Map source
    if "source" in invoice_doc:
        doc["source"] = invoice_doc["source"]
    
    # Map status (required at root)
    if "status" in invoice_doc:
        doc["status"] = invoice_doc["status"]
    
    # Map audit fields
    if "audit" not in invoice_doc:
        doc["audit"] = {
            "created_at": invoice_doc.get("created_at") or "",
            "updated_at": invoice_doc.get("updated_at") or ""
        }
    else:
        doc["audit"] = invoice_doc["audit"]
    
    # Map optional fields that are in the schema
    for field in ["document", "header", "lines", "workflow", "extensions"]:
        if field in invoice_doc:
            doc[field] = invoice_doc[field]
    
    return doc


def validate_received_invoice(invoice_doc: dict) -> Tuple[bool, List[str]]:
    """
    Validate a RECEIVED invoice against full canonical schema.
    
    Args:
        invoice_doc: Invoice document to validate
        
    Returns:
        Tuple of (is_valid: bool, errors: List[str])
        - If valid: (True, [])
        - If invalid: (False, ["field.path: error message", ...])
    """
    # Normalize for schema validation
    normalized = _normalize_for_schema(invoice_doc)
    
    validator = get_validator()
    errors = []
    
    # Validate against the full schema (which includes status-specific rules in allOf)
    for error in validator.iter_errors(normalized):
        # Format: field.path: message
        path_str = ".".join(str(p) for p in error.path) if error.path else ""
        if path_str:
            error_msg = f"{path_str}: {error.message}"
        else:
            error_msg = error.message
        errors.append(error_msg)
    
    return (len(errors) == 0, errors)


def validate_draft_invoice_minimal(invoice_doc: dict) -> Tuple[bool, List[str]]:
    """
    Lightweight validation for DRAFT invoices.
    
    Only checks that required top-level fields for DRAFT status are present:
    - identity (with invoice_id, tenant_id, trace_id)
    - source (with system, received_at)
    - status = "DRAFT"
    - audit (with created_at, updated_at)
    
    Args:
        invoice_doc: Invoice document to validate
        
    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []
    
    # Check status is DRAFT
    status = invoice_doc.get("status")
    if status != "DRAFT":
        errors.append(f"status: Expected 'DRAFT', got '{status}'")
        return (False, errors)
    
    # Check required top-level fields
    required_fields = ["identity", "source", "status", "audit"]
    for field in required_fields:
        if field not in invoice_doc:
            errors.append(f"{field}: Missing required field")
    
    # Check identity structure (lightweight)
    if "identity" in invoice_doc:
        identity = invoice_doc["identity"]
        if not isinstance(identity, dict):
            errors.append("identity: Must be an object")
        else:
            for id_field in ["invoice_id", "tenant_id", "trace_id"]:
                if id_field not in identity:
                    errors.append(f"identity.{id_field}: Missing required field")
    
    # Check source structure (lightweight)
    if "source" in invoice_doc:
        source = invoice_doc["source"]
        if not isinstance(source, dict):
            errors.append("source: Must be an object")
        else:
            for src_field in ["system", "received_at"]:
                if src_field not in source:
                    errors.append(f"source.{src_field}: Missing required field")
    
    # Check audit structure (lightweight)
    if "audit" in invoice_doc:
        audit = invoice_doc["audit"]
        if not isinstance(audit, dict):
            errors.append("audit: Must be an object")
        else:
            for audit_field in ["created_at", "updated_at"]:
                if audit_field not in audit:
                    errors.append(f"audit.{audit_field}: Missing required field")
    
    return (len(errors) == 0, errors)
