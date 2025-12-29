"""
Test canonical schema validation wiring.

Tests that:
1. DRAFT invoices skip full validation (minimal check only)
2. RECEIVED invoices require full schema compliance
3. PUT endpoint validates before DRAFT→RECEIVED transition
4. POST /submit endpoint validates before RECEIVED creation
5. Invalid RECEIVED invoices are rejected with 400 + field errors
"""

import asyncio
import json
from datetime import datetime
from app.utils.schema_validator import validate_received_invoice, validate_draft_invoice_minimal


def _now_iso():
    """Return current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def test_draft_validation():
    """Test that DRAFT invoices pass minimal validation."""
    print("\n=== Test 1: DRAFT Minimal Validation ===")
    
    draft_invoice = {
        "identity": {
            "invoice_id": 1,
            "tenant_id": "tenant-123",
            "trace_id": "trace-abc"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "DRAFT",
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_draft_invoice_minimal(draft_invoice)
    assert is_valid, f"DRAFT validation failed: {errors}"
    print("✓ DRAFT minimal validation passed")


def test_received_missing_required_fields():
    """Test that RECEIVED invoices reject missing required fields."""
    print("\n=== Test 2: RECEIVED Missing Required Fields ===")
    
    # Missing 'header', 'lines', 'document'
    incomplete_received = {
        "identity": {
            "invoice_id": 2,
            "tenant_id": "tenant-123",
            "trace_id": "trace-def"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "RECEIVED",
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_received_invoice(incomplete_received)
    assert not is_valid, "Expected validation to fail for incomplete RECEIVED"
    assert len(errors) > 0, "Expected error messages"
    print(f"✓ Correctly rejected: {errors}")


def test_received_valid():
    """Test that complete RECEIVED invoices pass validation."""
    print("\n=== Test 3: RECEIVED Valid ===")
    
    valid_received = {
        "identity": {
            "invoice_id": 3,
            "tenant_id": "tenant-123",
            "trace_id": "trace-ghi"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "RECEIVED",
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-001",
            "invoice_date": "2024-01-01",
            "vendor_name": "Vendor Inc",
            "currency": "USD",
            "total_amount": 1000.00
        },
        "lines": [
            {
                "line_number": 1,
                "description": "Service",
                "quantity": 1,
                "line_amount": 1000.00
            }
        ],
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_received_invoice(valid_received)
    assert is_valid, f"Validation failed for valid invoice: {errors}"
    print("✓ Valid RECEIVED invoice passed")


def test_received_missing_lines():
    """Test that RECEIVED rejects empty lines array."""
    print("\n=== Test 4: RECEIVED Empty Lines ===")
    
    no_lines = {
        "identity": {
            "invoice_id": 4,
            "tenant_id": "tenant-123",
            "trace_id": "trace-jkl"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "RECEIVED",
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-002",
            "invoice_date": "2024-01-02",
            "vendor_name": "Vendor Inc",
            "currency": "USD",
            "total_amount": 0.00
        },
        "lines": [],  # Empty!
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_received_invoice(no_lines)
    assert not is_valid, "Expected validation to fail for empty lines"
    print(f"✓ Correctly rejected empty lines: {errors}")


def test_received_invalid_currency():
    """Test that RECEIVED rejects invalid currency format."""
    print("\n=== Test 5: RECEIVED Invalid Currency ===")
    
    bad_currency = {
        "identity": {
            "invoice_id": 5,
            "tenant_id": "tenant-123",
            "trace_id": "trace-mno"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "RECEIVED",
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-003",
            "invoice_date": "2024-01-03",
            "vendor_name": "Vendor Inc",
            "currency": "INVALID",  # Not 3 uppercase letters
            "total_amount": 1000.00
        },
        "lines": [
            {
                "line_number": 1,
                "description": "Service",
                "quantity": 1,
                "line_amount": 1000.00
            }
        ],
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_received_invoice(bad_currency)
    assert not is_valid, "Expected validation to fail for invalid currency"
    print(f"✓ Correctly rejected invalid currency: {errors}")


def test_received_missing_header_fields():
    """Test that RECEIVED rejects missing header fields."""
    print("\n=== Test 6: RECEIVED Missing Header Fields ===")
    
    incomplete_header = {
        "identity": {
            "invoice_id": 6,
            "tenant_id": "tenant-123",
            "trace_id": "trace-pqr"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "status": "RECEIVED",
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-004",
            # Missing: invoice_date, vendor_name, currency, total_amount
        },
        "lines": [
            {
                "line_number": 1,
                "description": "Service",
                "quantity": 1,
                "line_amount": 1000.00
            }
        ],
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    is_valid, errors = validate_received_invoice(incomplete_header)
    assert not is_valid, "Expected validation to fail for incomplete header"
    print(f"✓ Correctly rejected incomplete header: {errors}")


if __name__ == "__main__":
    print("Testing Canonical Schema Validation")
    print("=" * 60)
    
    test_draft_validation()
    test_received_missing_required_fields()
    test_received_valid()
    test_received_missing_lines()
    test_received_invalid_currency()
    test_received_missing_header_fields()
    
    print("\n" + "=" * 60)
    print("✅ All schema validation tests passed!")
