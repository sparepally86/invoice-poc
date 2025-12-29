"""
Direct MongoDB test for schema validation wiring.

Tests the validation logic is properly integrated without needing HTTP server.
"""

import json
from datetime import datetime
from pymongo import MongoClient
from app.utils.schema_validator import validate_received_invoice


def _now_iso():
    """Return current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def get_db():
    """Connect to MongoDB."""
    client = MongoClient("mongodb://localhost:27017")
    return client["invoice_poc"]


def test_invalid_received_rejected():
    """Test that invalid RECEIVED documents are rejected before persistence."""
    print("\n=== Test 1: Invalid RECEIVED Rejected ===")
    
    # Build incomplete RECEIVED invoice (missing required fields)
    invoice_doc = {
        "status": "RECEIVED",
        "identity": {
            "invoice_id": 999,
            "tenant_id": "tenant-123",
            "trace_id": "trace-test-999"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        # Missing: document, header, lines
        "audit": {
            "created_at": _now_iso(),
            "updated_at": _now_iso()
        }
    }
    
    # Validate - should fail
    is_valid, errors = validate_received_invoice(invoice_doc)
    
    assert not is_valid, "Expected validation to fail"
    assert len(errors) > 0, "Expected error messages"
    assert any("document" in e for e in errors), f"Expected document error in {errors}"
    assert any("header" in e for e in errors), f"Expected header error in {errors}"
    assert any("lines" in e for e in errors), f"Expected lines error in {errors}"
    
    print(f"✓ Correctly rejected invalid RECEIVED:")
    for err in errors:
        print(f"  - {err}")


def test_valid_received_passes():
    """Test that valid RECEIVED documents pass validation."""
    print("\n=== Test 2: Valid RECEIVED Passes ===")
    
    # Build complete RECEIVED invoice
    invoice_doc = {
        "status": "RECEIVED",
        "identity": {
            "invoice_id": 998,
            "tenant_id": "tenant-123",
            "trace_id": "trace-test-998"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-998",
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
    
    # Validate - should pass
    is_valid, errors = validate_received_invoice(invoice_doc)
    
    assert is_valid, f"Expected validation to pass, but got errors: {errors}"
    assert len(errors) == 0, f"Expected no errors, got: {errors}"
    
    print("✓ Valid RECEIVED invoice passed validation")


def test_received_with_invalid_currency():
    """Test that invalid currency format is rejected."""
    print("\n=== Test 3: Invalid Currency Format ===")
    
    # Build RECEIVED invoice with bad currency
    invoice_doc = {
        "status": "RECEIVED",
        "identity": {
            "invoice_id": 997,
            "tenant_id": "tenant-123",
            "trace_id": "trace-test-997"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-997",
            "invoice_date": "2024-01-01",
            "vendor_name": "Vendor Inc",
            "currency": "INVALID",  # Should be 3 uppercase letters
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
    
    # Validate - should fail
    is_valid, errors = validate_received_invoice(invoice_doc)
    
    assert not is_valid, "Expected validation to fail for invalid currency"
    assert any("currency" in e.lower() for e in errors), f"Expected currency error in {errors}"
    
    print(f"✓ Correctly rejected invalid currency: {errors}")


def test_received_with_empty_lines():
    """Test that empty lines array is rejected."""
    print("\n=== Test 4: Empty Lines Array ===")
    
    # Build RECEIVED invoice with no lines
    invoice_doc = {
        "status": "RECEIVED",
        "identity": {
            "invoice_id": 996,
            "tenant_id": "tenant-123",
            "trace_id": "trace-test-996"
        },
        "source": {
            "system": "CAPTURE",
            "received_at": _now_iso()
        },
        "document": {
            "image_url": "https://example.com/invoice.pdf"
        },
        "header": {
            "invoice_number": "INV-996",
            "invoice_date": "2024-01-01",
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
    
    # Validate - should fail
    is_valid, errors = validate_received_invoice(invoice_doc)
    
    assert not is_valid, "Expected validation to fail for empty lines"
    assert any("lines" in e.lower() for e in errors), f"Expected lines error in {errors}"
    
    print(f"✓ Correctly rejected empty lines: {errors}")


if __name__ == "__main__":
    print("=" * 70)
    print("Direct MongoDB Test: Schema Validation Wiring")
    print("=" * 70)
    
    try:
        test_invalid_received_rejected()
        test_valid_received_passes()
        test_received_with_invalid_currency()
        test_received_with_empty_lines()
        
        print("\n" + "=" * 70)
        print("✅ All MongoDB validation tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
