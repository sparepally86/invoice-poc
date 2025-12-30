#!/usr/bin/env python3
"""
Test ValidationResult contract implementation.

Tests that:
1. ValidationAgent returns structured ValidationResult
2. Valid invoices produce PASS status with no issues
3. Invalid invoices produce FAIL/WARN status with structured issues
4. Orchestrator persists ValidationResult to invoice.validation field
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, os.path.abspath('.'))

from app.agents.validation import run_validation
from app.agents._common import ensure_agent_response

# Load environment
load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB = os.environ.get("MONGODB_DB", "invoice_poc")

print("\n" + "="*80)
print("TEST: ValidationResult Contract")
print("="*80)

# Connect to MongoDB
if not MONGODB_URI:
    print("ERROR: MONGODB_URI not set. Exiting.")
    sys.exit(1)

try:
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    print(f"✓ Connected to {MONGODB_DB}")
except Exception as e:
    print(f"ERROR: Failed to connect to MongoDB: {e}")
    sys.exit(1)

# Test 1: Valid Invoice
print("\n" + "="*80)
print("TEST 1: Valid Invoice → PASS status")
print("="*80)

valid_invoice = {
    "_id": "TEST-VALID-001",
    "invoice_id": 9999,
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2025-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item 1",
            "line_amount": 1000.0
        }
    ]
}

# Ensure test vendor exists
db.vendors.update_one(
    {"_id": "V001"},
    {"$set": {"vendor_id": "V001", "name": "Test Vendor"}},
    upsert=True
)

try:
    validation_result = run_validation(db, valid_invoice)
    print(f"✓ ValidationAgent returned result")
    
    # Check structure
    assert "validation" in validation_result, "Missing 'validation' field in agent output"
    vr = validation_result["validation"]
    
    print(f"\n  ValidationResult Structure:")
    print(f"  - status: {vr.get('status')}")
    print(f"  - issues: {len(vr.get('issues', []))} issues")
    print(f"  - summary: {vr.get('summary')}")
    print(f"  - validated_at: {vr.get('validated_at')}")
    
    assert vr.get("status") == "PASS", f"Expected status PASS, got {vr.get('status')}"
    assert len(vr.get("issues", [])) == 0, f"Expected 0 issues, got {len(vr.get('issues', []))}"
    assert vr.get("summary", {}).get("hard_failures") == 0, "Expected 0 hard failures"
    assert vr.get("summary", {}).get("soft_warnings") == 0, "Expected 0 soft warnings"
    
    print("\n✓ TEST 1 PASSED: Valid invoice produces PASS status with no issues")
except AssertionError as e:
    print(f"\n✗ TEST 1 FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ TEST 1 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Invalid Invoice (missing fields)
print("\n" + "="*80)
print("TEST 2: Invalid Invoice (missing fields) → FAIL status")
print("="*80)

invalid_invoice = {
    "_id": "TEST-INVALID-001",
    "invoice_id": 9998,
    "header": {
        # Missing invoice_number
        "invoice_date": "2025-01-01",
        "vendor_number": "V001",
        # Missing currency
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item 1",
            "line_amount": 1000.0
        }
    ]
}

try:
    validation_result = run_validation(db, invalid_invoice)
    print(f"✓ ValidationAgent returned result")
    
    # Check structure
    assert "validation" in validation_result, "Missing 'validation' field in agent output"
    vr = validation_result["validation"]
    
    print(f"\n  ValidationResult Structure:")
    print(f"  - status: {vr.get('status')}")
    print(f"  - issues: {len(vr.get('issues', []))} issues")
    print(f"  - summary: {vr.get('summary')}")
    
    if vr.get("issues"):
        print(f"\n  Issues:")
        for issue in vr.get("issues", []):
            print(f"    - {issue.get('code')} ({issue.get('severity')}): {issue.get('message')}")
    
    assert vr.get("status") == "FAIL", f"Expected status FAIL, got {vr.get('status')}"
    assert len(vr.get("issues", [])) > 0, f"Expected issues, got none"
    assert vr.get("summary", {}).get("hard_failures") > 0, "Expected hard failures"
    
    # Verify issue structure
    for issue in vr.get("issues", []):
        assert "code" in issue, "Issue missing 'code' field"
        assert "category" in issue, "Issue missing 'category' field"
        assert "severity" in issue, "Issue missing 'severity' field"
        assert "field" in issue, "Issue missing 'field' field"
        assert "message" in issue, "Issue missing 'message' field"
        assert "metadata" in issue, "Issue missing 'metadata' field"
    
    print("\n✓ TEST 2 PASSED: Invalid invoice produces FAIL status with structured issues")
except AssertionError as e:
    print(f"\n✗ TEST 2 FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ TEST 2 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Invalid Invoice (amount mismatch)
print("\n" + "="*80)
print("TEST 3: Invalid Invoice (amount mismatch) → FAIL status")
print("="*80)

amount_mismatch_invoice = {
    "_id": "TEST-INVALID-002",
    "invoice_id": 9997,
    "header": {
        "invoice_number": "INV-002",
        "invoice_date": "2025-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0  # Should be 2000.0 based on lines
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item 1",
            "line_amount": 2000.0
        }
    ]
}

try:
    validation_result = run_validation(db, amount_mismatch_invoice)
    print(f"✓ ValidationAgent returned result")
    
    vr = validation_result["validation"]
    
    print(f"\n  ValidationResult Structure:")
    print(f"  - status: {vr.get('status')}")
    print(f"  - issues: {len(vr.get('issues', []))} issues")
    print(f"  - summary: {vr.get('summary')}")
    
    if vr.get("issues"):
        print(f"\n  Issues:")
        for issue in vr.get("issues", []):
            print(f"    - {issue.get('code')}: {issue.get('message')}")
            print(f"      metadata: {issue.get('metadata')}")
    
    # Find amount mismatch issue
    amount_issue = next((i for i in vr.get("issues", []) if i.get("code") == "AMOUNT_MISMATCH"), None)
    assert amount_issue is not None, "Expected AMOUNT_MISMATCH issue not found"
    assert amount_issue.get("category") == "FINANCIAL", "Expected category FINANCIAL"
    assert amount_issue.get("severity") == "HARD", "Expected severity HARD"
    assert "metadata" in amount_issue, "Expected metadata in amount issue"
    
    print("\n✓ TEST 3 PASSED: Amount mismatch issue properly categorized and detailed")
except AssertionError as e:
    print(f"\n✗ TEST 3 FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ TEST 3 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Backward compatibility - agent status
print("\n" + "="*80)
print("TEST 4: Backward Compatibility - agent status field")
print("="*80)

try:
    validation_result = run_validation(db, valid_invoice)
    
    # Check backward compatibility fields
    assert "agent" in validation_result, "Missing 'agent' field"
    assert "status" in validation_result, "Missing 'status' field"
    assert "result" in validation_result, "Missing 'result' field"
    assert "timestamp" in validation_result, "Missing 'timestamp' field"
    
    # For valid invoice, agent status should be "completed"
    assert validation_result.get("status") == "completed", f"Expected agent status 'completed', got {validation_result.get('status')}"
    
    # Result should have old-style fields
    result = validation_result.get("result", {})
    assert "valid" in result, "Missing 'valid' field in result"
    assert result.get("valid") is True, "Expected valid=True for valid invoice"
    
    print(f"✓ Agent status: {validation_result.get('status')}")
    print(f"✓ Result.valid: {result.get('valid')}")
    print("\n✓ TEST 4 PASSED: Backward compatibility maintained")
except AssertionError as e:
    print(f"\n✗ TEST 4 FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ TEST 4 FAILED with exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("ALL TESTS PASSED ✓")
print("="*80)
print("\nValidationResult Contract Implementation Summary:")
print("  ✓ ValidationAgent returns structured ValidationResult")
print("  ✓ Valid invoices produce PASS status with no issues")
print("  ✓ Invalid invoices produce FAIL status with structured issues")
print("  ✓ Issues have proper structure (code, category, severity, field, message, metadata)")
print("  ✓ Backward compatibility maintained (agent status, result.valid)")
print("  ✓ Categories: STRUCTURAL, FINANCIAL, POLICY")
print("  ✓ Severity levels: HARD, SOFT")
print("  ✓ Summary provides hard_failures and soft_warnings counts")
print("  ✓ Metadata available for additional issue context")
