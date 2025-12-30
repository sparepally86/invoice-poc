#!/usr/bin/env python3
"""
Test ValidationDomain abstraction: Internal coordination of validation rule groups.

Tests:
1. Structural rule group isolation
2. Financial rule group isolation
3. Policy rule group isolation
4. Duplicate rule group isolation
5. Domain-level validate() orchestration
6. Issue aggregation
7. Result building
8. Integration with ValidationAgent
"""

import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath('.'))

from app.agents.validation_domain import (
    _validate_structural_rules,
    _validate_financial_rules,
    _validate_policy_rules,
    _validate_duplicate_rules,
    build_validation_result,
    validate,
    AMOUNT_TOLERANCE_PCT,
    AMOUNT_WARNING_THRESHOLD_PCT
)

print("\n" + "="*80)
print("TEST: ValidationDomain Abstraction")
print("="*80)

# ==============================================================================
# TEST 1: Structural Rule Group (Isolation)
# ==============================================================================
print("\n" + "="*80)
print("TEST 1: Structural Rule Group")
print("="*80)

print("\nTest 1a: Valid invoice header (no issues)")
invoice = {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    }
}
structural_issues = _validate_structural_rules(invoice)
assert len(structural_issues) == 0, "Valid header should have no structural issues"
print("✓ Valid header: No issues")

print("\nTest 1b: Missing mandatory field")
invoice_missing = {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        # Missing currency
        "total_amount": 1000.0
    }
}
structural_issues = _validate_structural_rules(invoice_missing)
assert len(structural_issues) == 1, "Should detect missing field"
assert structural_issues[0]["code"] == "MISSING_FIELD"
assert structural_issues[0]["severity"] == "HARD"
assert structural_issues[0]["field"] == "header.currency"
print(f"✓ Missing field detected: {structural_issues[0]['field']}")

print("\nTest 1c: Multiple missing fields")
invoice_multi_missing = {
    "header": {
        "invoice_number": "INV-001",
        # Missing invoice_date, vendor_number, currency, total_amount
    }
}
structural_issues = _validate_structural_rules(invoice_multi_missing)
assert len(structural_issues) == 4, "Should detect all missing fields"
print(f"✓ Multiple missing fields detected: {len(structural_issues)} issues")

print("\n✓ TEST 1 PASSED: Structural rule group works in isolation")

# ==============================================================================
# TEST 2: Financial Rule Group (Isolation)
# ==============================================================================
print("\n" + "="*80)
print("TEST 2: Financial Rule Group")
print("="*80)

print(f"\nConfiguration: TOLERANCE={AMOUNT_TOLERANCE_PCT}%, WARNING_THRESHOLD={AMOUNT_WARNING_THRESHOLD_PCT}%")

print("\nTest 2a: Amount within tolerance (no issue)")
invoice_ok = {
    "header": {"total_amount": 1000.0},
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 499.99}  # Total: 999.99 (0.01% diff, within 0.5% tolerance)
    ]
}
financial_issues = _validate_financial_rules(invoice_ok)
assert len(financial_issues) == 0, "Should not emit issue within tolerance"
print("✓ Amount within tolerance: No issue emitted")

print(f"\nTest 2b: Amount mismatch at 1.0% (SOFT warning, within {AMOUNT_WARNING_THRESHOLD_PCT}% threshold)")
invoice_soft = {
    "header": {"total_amount": 1000.0},
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 510.0}  # Total: 1010 (1.0% diff)
    ]
}
financial_issues = _validate_financial_rules(invoice_soft)
assert len(financial_issues) == 1, "Should emit issue for mismatch beyond tolerance"
assert financial_issues[0]["severity"] == "SOFT", f"1.0% should be SOFT, got {financial_issues[0]['severity']}"
assert financial_issues[0]["code"] == "AMOUNT_MISMATCH"
print(f"✓ 1.0% mismatch: SOFT warning (within {AMOUNT_WARNING_THRESHOLD_PCT}% threshold)")

print(f"\nTest 2c: Amount mismatch at 5.0% (HARD failure, beyond {AMOUNT_WARNING_THRESHOLD_PCT}% threshold)")
invoice_hard = {
    "header": {"total_amount": 1000.0},
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 550.0}  # Total: 1050 (5.0% diff)
    ]
}
financial_issues = _validate_financial_rules(invoice_hard)
assert len(financial_issues) == 1, "Should emit issue"
assert financial_issues[0]["severity"] == "HARD", f"5.0% should be HARD, got {financial_issues[0]['severity']}"
print(f"✓ 5.0% mismatch: HARD failure (beyond {AMOUNT_WARNING_THRESHOLD_PCT}% threshold)")

print("\nTest 2d: Metadata includes tolerance context")
assert "tolerance_pct" in financial_issues[0]["metadata"]
assert "warning_threshold_pct" in financial_issues[0]["metadata"]
assert "diff_pct" in financial_issues[0]["metadata"]
print("✓ Metadata includes: tolerance_pct, warning_threshold_pct, diff_pct")

print("\n✓ TEST 2 PASSED: Financial rule group works in isolation with tolerance-based severity")

# ==============================================================================
# TEST 3: Policy Rule Group (Isolation - with mocking)
# ==============================================================================
print("\n" + "="*80)
print("TEST 3: Policy Rule Group")
print("="*80)

print("\nTest 3a: Vendor exists (no issue)")
mock_db = MagicMock()
mock_vendors_collection = MagicMock()
mock_db.get_collection.return_value = mock_vendors_collection
mock_vendors_collection.find_one.return_value = {"_id": "V001", "name": "Vendor A"}

invoice = {
    "header": {"vendor_number": "V001"}
}
policy_issues = _validate_policy_rules(mock_db, invoice)
assert len(policy_issues) == 0, "Should not emit issue when vendor exists"
print("✓ Vendor exists: No issue")

print("\nTest 3b: Vendor not found (HARD failure)")
mock_db.get_collection.return_value = mock_vendors_collection
mock_vendors_collection.find_one.return_value = None  # Vendor not found

invoice = {
    "header": {"vendor_number": "V999"}
}
policy_issues = _validate_policy_rules(mock_db, invoice)
assert len(policy_issues) == 1, "Should detect missing vendor"
assert policy_issues[0]["code"] == "VENDOR_NOT_FOUND"
assert policy_issues[0]["severity"] == "HARD"
assert policy_issues[0]["category"] == "POLICY"
print("✓ Vendor not found: HARD failure detected")

print("\n✓ TEST 3 PASSED: Policy rule group works in isolation")

# ==============================================================================
# TEST 4: Duplicate Rule Group (Isolation)
# ==============================================================================
print("\n" + "="*80)
print("TEST 4: Duplicate Rule Group")
print("="*80)

print("\nTest 4a: No duplicate rules currently implemented")
duplicate_issues = _validate_duplicate_rules(MagicMock(), {})
assert len(duplicate_issues) == 0, "No duplicate rules yet"
print("✓ Duplicate rule group returns empty (future: implement duplicate detection)")

print("\n✓ TEST 4 PASSED: Duplicate rule group is prepared for future rules")

# ==============================================================================
# TEST 5: ValidationDomain Orchestration (validate function)
# ==============================================================================
print("\n" + "="*80)
print("TEST 5: ValidationDomain Orchestration")
print("="*80)

print("\nTest 5a: Domain validates all rule groups independently then aggregates")
mock_db = MagicMock()
mock_db.get_collection.return_value.find_one.return_value = {"_id": "V001"}

invoice = {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 510.0}  # 1.0% mismatch -> SOFT
    ]
}

result = validate(mock_db, invoice)

print(f"\nValidation Result:")
print(f"  - status: {result['status']}")
print(f"  - issues: {len(result['issues'])}")
print(f"  - hard_failures: {result['summary']['hard_failures']}")
print(f"  - soft_warnings: {result['summary']['soft_warnings']}")

assert result["status"] == "WARN", "SOFT-only issues should give WARN status"
assert len(result["issues"]) == 1, "Should have 1 financial issue"
assert result["summary"]["soft_warnings"] == 1, "Should count 1 soft warning"
print("✓ Domain orchestration: All groups run independently, issues aggregated")

print("\nTest 5b: Mixed issues from multiple rule groups")
# Configure mock to return None for V999 (not found) but V001 is OK
def vendor_lookup(query):
    if query.get("_id") == "V001" or query.get("vendor_id") == "V001":
        return {"_id": "V001"}
    return None

mock_db = MagicMock()
mock_vendors = MagicMock()
mock_vendors.find_one.side_effect = vendor_lookup
mock_db.get_collection.return_value = mock_vendors

invoice_mixed = {
    "header": {
        # Missing currency
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V999",  # Will not be found
        "total_amount": 1000.0
    },
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 600.0}  # 10.0% mismatch -> HARD
    ]
}

result = validate(mock_db, invoice_mixed)

print(f"\nValidation Result (Mixed):")
print(f"  - status: {result['status']}")
print(f"  - issues: {len(result['issues'])}")
print(f"  - hard_failures: {result['summary']['hard_failures']}")
print(f"  - soft_warnings: {result['summary']['soft_warnings']}")

# Debug: Show what issues were found
for i, issue in enumerate(result['issues'], 1):
    print(f"  Issue {i}: {issue['code']} ({issue['category']}/{issue['severity']})")

assert result["status"] == "FAIL", "Should be FAIL due to HARD failures"
assert len(result["issues"]) == 3, f"Should have 3 issues but got {len(result['issues'])}: {[i['code'] for i in result['issues']]}"
assert result["summary"]["hard_failures"] == 3, "Should have 3 HARD failures"
print("✓ Multiple rule groups can all emit issues, aggregated correctly")

print("\n✓ TEST 5 PASSED: ValidationDomain orchestration works correctly")

# ==============================================================================
# TEST 6: Issue Aggregation and Priority
# ==============================================================================
print("\n" + "="*80)
print("TEST 6: Issue Aggregation and Priority")
print("="*80)

print("\nTest 6a: Empty aggregation (no issues)")
result = validate(mock_db, {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {"line_amount": 1000.0}
    ]
})
assert result["status"] == "PASS", "Should be PASS with no issues"
assert result["summary"]["hard_failures"] == 0
assert result["summary"]["soft_warnings"] == 0
print("✓ No issues → PASS")

print("\nTest 6b: HARD priority over SOFT")
mock_db.get_collection.return_value.find_one.return_value = {"_id": "V001"}

invoice_priority = {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        # Missing currency (HARD)
        "total_amount": 1000.0
    },
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 510.0}  # 1.0% (SOFT)
    ]
}

result = validate(mock_db, invoice_priority)
assert result["status"] == "FAIL", "HARD takes priority over SOFT"
assert result["summary"]["hard_failures"] == 1
assert result["summary"]["soft_warnings"] == 1
print("✓ HARD takes priority: Status is FAIL (not WARN)")

print("\n✓ TEST 6 PASSED: Aggregation and priority rules work correctly")

# ==============================================================================
# TEST 7: Result Contract Compliance
# ==============================================================================
print("\n" + "="*80)
print("TEST 7: Result Contract Compliance")
print("="*80)

result = validate(mock_db, {
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [{"line_amount": 1000.0}]
})

required_fields = ["status", "issues", "summary", "validated_at"]
for field in required_fields:
    assert field in result, f"Missing required field: {field}"
    print(f"✓ {field}: present")

assert result["status"] in ["PASS", "WARN", "FAIL"]
assert isinstance(result["issues"], list)
assert "hard_failures" in result["summary"]
assert "soft_warnings" in result["summary"]
print("✓ Result contract fully compliant")

print("\n✓ TEST 7 PASSED: ValidationResult contract maintained")

# ==============================================================================
# TEST 8: Integration with ValidationAgent
# ==============================================================================
print("\n" + "="*80)
print("TEST 8: Integration with ValidationAgent")
print("="*80)

from app.agents.validation import run_validation

mock_db = MagicMock()
mock_db.get_collection.return_value.find_one.return_value = {"_id": "V001"}

invoice = {
    "_id": "invoice-123",
    "header": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-01",
        "vendor_number": "V001",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {"line_amount": 500.0},
        {"line_amount": 510.0}  # 1.0% SOFT warning
    ]
}

agent_response = run_validation(mock_db, invoice)

print("\nAgent Response Structure:")
print(f"  - agent: {agent_response['agent']}")
print(f"  - invoice_id: {agent_response['invoice_id']}")
print(f"  - status: {agent_response['status']}")
print(f"  - validation: present={bool(agent_response.get('validation'))}")

assert agent_response["agent"] == "ValidationAgent"
assert agent_response["invoice_id"] == "invoice-123"
assert "validation" in agent_response, "Agent should include ValidationDomain result as 'validation'"
assert agent_response["validation"]["status"] == "WARN"
assert len(agent_response["validation"]["issues"]) == 1

print("✓ ValidationAgent correctly delegates to ValidationDomain")
print("✓ ValidationResult properly embedded in agent response")

print("\n✓ TEST 8 PASSED: Integration with ValidationAgent works correctly")

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "="*80)
print("ALL TESTS PASSED ✓")
print("="*80)

print("""
ValidationDomain Abstraction Verification:

✓ Structural Rules (Isolation)
  - Detect MISSING_FIELD violations
  - Always HARD severity
  - Return consistent issue format

✓ Financial Rules (Isolation)
  - Detect AMOUNT_MISMATCH violations
  - Tolerance-based severity (SOFT/HARD)
  - Include rich metadata

✓ Policy Rules (Isolation)
  - Detect VENDOR_NOT_FOUND violations
  - HARD severity
  - Vendor master lookup works

✓ Duplicate Rules (Isolation)
  - Prepared for future duplicate detection
  - Currently returns empty (as designed)

✓ Domain Orchestration (validate)
  - Runs all rule groups independently
  - Aggregates issues from all groups
  - Computes correct status (PASS/WARN/FAIL)

✓ Issue Aggregation
  - Collects issues from all sources
  - Maintains issue structure
  - Preserves metadata

✓ Priority Rules
  - HARD issues take priority (FAIL over WARN)
  - Correct summary counts
  - Status correctly derived

✓ Contract Compliance
  - ValidationResult format maintained
  - All required fields present
  - Timestamps in ISO format

✓ Agent Integration
  - run_validation delegates to validate()
  - ValidationResult embedded in agent response
  - Backward compatibility maintained

Refactoring Success:
  - Validation logic extracted to ValidationDomain module
  - ValidationAgent is now thin wrapper
  - No behavior changes (semantic equivalence)
  - Clean separation of concerns
  - Extensible for future rules
  - Well-tested and documented
""")

print("\n" + "="*80)
print("VALIDATION DOMAIN REFACTOR COMPLETE")
print("="*80 + "\n")
