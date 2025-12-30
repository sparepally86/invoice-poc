#!/usr/bin/env python3
"""
Unit test for ValidationResult contract (no server/MongoDB required).

Tests the structure and behavior of the ValidationResult without dependencies.
"""

import sys
import os
import json
from datetime import datetime

# Add app to path
sys.path.insert(0, os.path.abspath('.'))

print("\n" + "="*80)
print("UNIT TEST: ValidationResult Contract Structure")
print("="*80)

# Test the _build_validation_result function directly
from app.agents.validation_domain import build_validation_result

# Test 1: No issues → PASS
print("\n" + "="*80)
print("TEST 1: No issues → PASS status")
print("="*80)

issues = []
validated_at = datetime.utcnow().isoformat() + "Z"
vr = build_validation_result(issues, validated_at)

print(f"Status: {vr['status']}")
print(f"Issues: {vr['issues']}")
print(f"Summary: {vr['summary']}")
print(f"Validated at: {vr['validated_at']}")

assert vr["status"] == "PASS", f"Expected PASS, got {vr['status']}"
assert vr["issues"] == [], f"Expected no issues, got {vr['issues']}"
assert vr["summary"]["hard_failures"] == 0, "Expected 0 hard failures"
assert vr["summary"]["soft_warnings"] == 0, "Expected 0 soft warnings"
print("✓ TEST 1 PASSED")

# Test 2: HARD severity → FAIL
print("\n" + "="*80)
print("TEST 2: HARD severity issue → FAIL status")
print("="*80)

issues = [
    {
        "code": "MISSING_FIELD",
        "category": "STRUCTURAL",
        "severity": "HARD",
        "field": "header.invoice_number",
        "message": "invoice_number is missing",
        "metadata": {}
    }
]
vr = build_validation_result(issues, validated_at)

print(f"Status: {vr['status']}")
print(f"Issues: {len(vr['issues'])} issue(s)")
print(f"Summary: {vr['summary']}")

assert vr["status"] == "FAIL", f"Expected FAIL, got {vr['status']}"
assert len(vr["issues"]) == 1, f"Expected 1 issue, got {len(vr['issues'])}"
assert vr["summary"]["hard_failures"] == 1, "Expected 1 hard failure"
assert vr["summary"]["soft_warnings"] == 0, "Expected 0 soft warnings"
print("✓ TEST 2 PASSED")

# Test 3: SOFT severity only → WARN
print("\n" + "="*80)
print("TEST 3: SOFT severity only → WARN status")
print("="*80)

issues = [
    {
        "code": "DUPLICATE_PO",
        "category": "POLICY",
        "severity": "SOFT",
        "field": "header.po_number",
        "message": "PO has been used before",
        "metadata": {"previous_invoice_id": "INV-123"}
    }
]
vr = build_validation_result(issues, validated_at)

print(f"Status: {vr['status']}")
print(f"Issues: {len(vr['issues'])} issue(s)")
print(f"Summary: {vr['summary']}")

assert vr["status"] == "WARN", f"Expected WARN, got {vr['status']}"
assert len(vr["issues"]) == 1, f"Expected 1 issue, got {len(vr['issues'])}"
assert vr["summary"]["hard_failures"] == 0, "Expected 0 hard failures"
assert vr["summary"]["soft_warnings"] == 1, "Expected 1 soft warning"
print("✓ TEST 3 PASSED")

# Test 4: Multiple issues (mix of HARD and SOFT) → FAIL (HARD takes priority)
print("\n" + "="*80)
print("TEST 4: Mixed HARD and SOFT → FAIL (HARD priority)")
print("="*80)

issues = [
    {
        "code": "MISSING_FIELD",
        "category": "STRUCTURAL",
        "severity": "HARD",
        "field": "header.invoice_number",
        "message": "invoice_number is missing",
        "metadata": {}
    },
    {
        "code": "DUPLICATE_PO",
        "category": "POLICY",
        "severity": "SOFT",
        "field": "header.po_number",
        "message": "PO has been used before",
        "metadata": {}
    }
]
vr = build_validation_result(issues, validated_at)

print(f"Status: {vr['status']}")
print(f"Issues: {len(vr['issues'])} issue(s)")
print(f"Summary: {vr['summary']}")

assert vr["status"] == "FAIL", f"Expected FAIL, got {vr['status']}"
assert len(vr["issues"]) == 2, f"Expected 2 issues, got {len(vr['issues'])}"
assert vr["summary"]["hard_failures"] == 1, "Expected 1 hard failure"
assert vr["summary"]["soft_warnings"] == 1, "Expected 1 soft warning"
print("✓ TEST 4 PASSED")

# Test 5: Issue structure validation
print("\n" + "="*80)
print("TEST 5: Issue structure validation")
print("="*80)

issues = [
    {
        "code": "VENDOR_NOT_FOUND",
        "category": "POLICY",
        "severity": "HARD",
        "field": "header.vendor_number",
        "message": "Vendor 'V999' not found",
        "metadata": {"search_term": "V999"}
    }
]
vr = build_validation_result(issues, validated_at)

issue = vr["issues"][0]
required_fields = ["code", "category", "severity", "field", "message", "metadata"]

print(f"Issue fields: {list(issue.keys())}")

for field in required_fields:
    assert field in issue, f"Missing required field: {field}"
    print(f"  ✓ {field}: {issue[field]}")

# Test category values
valid_categories = ["STRUCTURAL", "FINANCIAL", "POLICY", "DUPLICATE"]
assert issue["category"] in valid_categories, f"Invalid category: {issue['category']}"

# Test severity values
valid_severities = ["HARD", "SOFT"]
assert issue["severity"] in valid_severities, f"Invalid severity: {issue['severity']}"

print("✓ TEST 5 PASSED")

# Test 6: Validated timestamp format
print("\n" + "="*80)
print("TEST 6: Validated timestamp format")
print("="*80)

issues = []
validated_at = datetime.utcnow().isoformat() + "Z"
vr = build_validation_result(issues, validated_at)

print(f"Timestamp: {vr['validated_at']}")
assert vr['validated_at'].endswith('Z'), "Timestamp should end with Z (UTC)"
print("✓ TEST 6 PASSED")

print("\n" + "="*80)
print("ALL UNIT TESTS PASSED ✓")
print("="*80)
print("\nValidationResult Contract Implementation:")
print("  ✓ Status correctly derived (PASS/WARN/FAIL)")
print("  ✓ Issues array with proper structure")
print("  ✓ Summary with hard_failures and soft_warnings counts")
print("  ✓ Categories: STRUCTURAL, FINANCIAL, POLICY, DUPLICATE")
print("  ✓ Severity levels: HARD, SOFT")
print("  ✓ Timestamps in ISO format with Z suffix")
print("  ✓ Optional metadata support")
