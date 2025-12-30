"""
Test suite for Step E3 - Policy Validation Rules

Tests all 4 policy rules:
- E3-P1: Allowed currency validation
- E3-P2: Invoice date window validation
- E3-P3: High amount threshold warning
- E3-P4: Country-specific mandatory fields

Verifies:
1. Each rule works independently
2. Violations emit correct severity (HARD/SOFT)
3. Multiple violations aggregate correctly
4. Backward compatibility with existing vendor check
"""

import sys
import os
import datetime
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.validation_domain import _validate_policy_rules, build_validation_result


class MockDB:
    """Mock MongoDB client for testing"""
    
    def __init__(self, vendors=None):
        self.vendors_data = vendors or {}
    
    def get_collection(self, name):
        if name == "vendors":
            return MockCollection(self.vendors_data)
        return MockCollection({})


class MockCollection:
    """Mock MongoDB collection"""
    
    def __init__(self, data):
        self.data = data
    
    def find_one(self, query):
        if "_id" in query:
            return self.data.get(query["_id"])
        if "vendor_id" in query:
            return self.data.get(query["vendor_id"])
        return None


def create_minimal_invoice(**header_overrides):
    """Create a minimal valid invoice for testing"""
    header = {
        "invoice_number": "INV-001",
        "invoice_date": datetime.datetime.utcnow().date().isoformat(),
        "vendor_number": "VND-001",
        "currency": "USD",
        "total_amount": 1000.0,
    }
    header.update(header_overrides)
    return {
        "header": header,
        "lines": [{"line_amount": 1000.0, "description": "Test line"}]
    }


def test_e3_p1_currency_allowed():
    """Test E3-P1: Valid currency - should NOT emit issue"""
    print("\n=== Test 1.1: E3-P1 - Allowed Currency ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(currency="USD")
    
    issues = _validate_policy_rules(db, invoice)
    
    # Filter to only E3-P1 issues
    p1_issues = [i for i in issues if i["code"] == "UNSUPPORTED_CURRENCY"]
    print(f"Issues found: {len(p1_issues)}")
    assert len(p1_issues) == 0, "Valid currency should not emit issue"
    print("✓ PASS: Valid currency accepted")


def test_e3_p1_currency_unsupported():
    """Test E3-P1: Unsupported currency - should emit HARD issue"""
    print("\n=== Test 1.2: E3-P1 - Unsupported Currency ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(currency="XYZ")
    
    issues = _validate_policy_rules(db, invoice)
    
    p1_issues = [i for i in issues if i["code"] == "UNSUPPORTED_CURRENCY"]
    assert len(p1_issues) == 1, "Unsupported currency should emit one issue"
    issue = p1_issues[0]
    assert issue["severity"] == "HARD", "Currency issue should be HARD"
    assert issue["category"] == "POLICY", "Issue category should be POLICY"
    print(f"Issue: {issue['message']}")
    print(f"Metadata: {issue['metadata']}")
    print("✓ PASS: Unsupported currency detected as HARD")


def test_e3_p1_multiple_currencies():
    """Test E3-P1: Test all supported currencies"""
    print("\n=== Test 1.3: E3-P1 - Multiple Supported Currencies ===")
    supported = ["INR", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]
    
    for curr in supported:
        db = MockDB({"VND-001": {"_id": "VND-001"}})
        invoice = create_minimal_invoice(currency=curr)
        issues = _validate_policy_rules(db, invoice)
        p1_issues = [i for i in issues if i["code"] == "UNSUPPORTED_CURRENCY"]
        assert len(p1_issues) == 0, f"Currency {curr} should be allowed"
    
    print(f"✓ PASS: All {len(supported)} supported currencies accepted")


def test_e3_p2_date_valid():
    """Test E3-P2: Valid invoice date - should NOT emit issue"""
    print("\n=== Test 2.1: E3-P2 - Valid Invoice Date ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    invoice = create_minimal_invoice(invoice_date=yesterday)
    
    issues = _validate_policy_rules(db, invoice)
    
    p2_issues = [i for i in issues if i["code"] == "INVALID_INVOICE_DATE"]
    print(f"Issues found: {len(p2_issues)}")
    assert len(p2_issues) == 0, "Recent date should not emit issue"
    print("✓ PASS: Valid date accepted")


def test_e3_p2_date_future():
    """Test E3-P2: Future invoice date - should emit HARD issue"""
    print("\n=== Test 2.2: E3-P2 - Future Invoice Date ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()
    invoice = create_minimal_invoice(invoice_date=tomorrow)
    
    issues = _validate_policy_rules(db, invoice)
    
    p2_issues = [i for i in issues if i["code"] == "INVALID_INVOICE_DATE"]
    assert len(p2_issues) == 1, "Future date should emit one issue"
    issue = p2_issues[0]
    assert issue["severity"] == "HARD", "Future date should be HARD"
    print(f"Issue: {issue['message']}")
    print("✓ PASS: Future date detected as HARD")


def test_e3_p2_date_old():
    """Test E3-P2: Old invoice date (>180 days) - should emit SOFT issue"""
    print("\n=== Test 2.3: E3-P2 - Old Invoice Date ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    old_date = (today - datetime.timedelta(days=185)).isoformat()
    invoice = create_minimal_invoice(invoice_date=old_date)
    
    issues = _validate_policy_rules(db, invoice)
    
    p2_issues = [i for i in issues if i["code"] == "INVALID_INVOICE_DATE"]
    assert len(p2_issues) == 1, "Old date should emit one issue"
    issue = p2_issues[0]
    assert issue["severity"] == "SOFT", "Old date should be SOFT"
    print(f"Issue: {issue['message']}")
    print(f"Days old: {issue['metadata']['days_old']}")
    print("✓ PASS: Old date detected as SOFT")


def test_e3_p2_date_boundary():
    """Test E3-P2: Date exactly at 180 day boundary"""
    print("\n=== Test 2.4: E3-P2 - Date at 180-Day Boundary ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    boundary = (today - datetime.timedelta(days=180)).isoformat()
    invoice = create_minimal_invoice(invoice_date=boundary)
    
    issues = _validate_policy_rules(db, invoice)
    
    p2_issues = [i for i in issues if i["code"] == "INVALID_INVOICE_DATE"]
    # At exactly 180 days, should NOT trigger (> 180, not >=)
    assert len(p2_issues) == 0, "Date at exactly 180 days should not trigger"
    print("✓ PASS: 180-day boundary handled correctly")


def test_e3_p3_high_amount_warn():
    """Test E3-P3: High amount - should emit SOFT issue"""
    print("\n=== Test 3.1: E3-P3 - High Value Invoice ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(total_amount=2_000_000.0)
    
    issues = _validate_policy_rules(db, invoice)
    
    p3_issues = [i for i in issues if i["code"] == "HIGH_VALUE_INVOICE"]
    assert len(p3_issues) == 1, "High amount should emit one issue"
    issue = p3_issues[0]
    assert issue["severity"] == "SOFT", "High amount should always be SOFT"
    print(f"Issue: {issue['message']}")
    print(f"Amount: {issue['metadata']['total_amount']}")
    print(f"Threshold: {issue['metadata']['threshold']}")
    print("✓ PASS: High amount detected as SOFT")


def test_e3_p3_high_amount_boundary():
    """Test E3-P3: Amount exactly at threshold"""
    print("\n=== Test 3.2: E3-P3 - Amount at Threshold ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(total_amount=1_000_000.0)
    
    issues = _validate_policy_rules(db, invoice)
    
    p3_issues = [i for i in issues if i["code"] == "HIGH_VALUE_INVOICE"]
    # At exactly 1M, should NOT trigger (>= not >)
    assert len(p3_issues) == 0, "Amount at exactly threshold should not trigger"
    print("✓ PASS: Threshold boundary handled correctly")


def test_e3_p3_normal_amount():
    """Test E3-P3: Normal amount - should NOT emit issue"""
    print("\n=== Test 3.3: E3-P3 - Normal Amount ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(total_amount=50_000.0)
    
    issues = _validate_policy_rules(db, invoice)
    
    p3_issues = [i for i in issues if i["code"] == "HIGH_VALUE_INVOICE"]
    assert len(p3_issues) == 0, "Normal amount should not emit issue"
    print("✓ PASS: Normal amount accepted")


def test_e3_p4_india_with_gstin():
    """Test E3-P4: India invoice with GSTIN - should NOT emit issue"""
    print("\n=== Test 4.1: E3-P4 - India with GSTIN ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="IN", gstin="18AABCT1234A1Z0")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 0, "India with GSTIN should not emit issue"
    print("✓ PASS: India GSTIN requirement satisfied")


def test_e3_p4_india_without_gstin():
    """Test E3-P4: India invoice without GSTIN - should emit HARD issue"""
    print("\n=== Test 4.2: E3-P4 - India without GSTIN ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="IN")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 1, "India without GSTIN should emit issue"
    issue = p4_issues[0]
    assert issue["severity"] == "HARD", "Missing GSTIN should be HARD"
    print(f"Issue: {issue['message']}")
    print(f"Required field: {issue['metadata']['required_field']}")
    print("✓ PASS: Missing GSTIN detected as HARD")


def test_e3_p4_india_empty_gstin():
    """Test E3-P4: India invoice with empty GSTIN - should emit HARD issue"""
    print("\n=== Test 4.3: E3-P4 - India with Empty GSTIN ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="IN", gstin="")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 1, "India with empty GSTIN should emit issue"
    print("✓ PASS: Empty GSTIN detected")


def test_e3_p4_us_with_tax_id():
    """Test E3-P4: US invoice with Tax ID - should NOT emit issue"""
    print("\n=== Test 4.4: E3-P4 - US with Tax ID ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="US", tax_id="12-3456789")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 0, "US with Tax ID should not emit issue"
    print("✓ PASS: US Tax ID requirement satisfied")


def test_e3_p4_us_without_tax_id():
    """Test E3-P4: US invoice without Tax ID - should emit HARD issue"""
    print("\n=== Test 4.5: E3-P4 - US without Tax ID ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="US")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 1, "US without Tax ID should emit issue"
    issue = p4_issues[0]
    assert issue["severity"] == "HARD", "Missing Tax ID should be HARD"
    print(f"Issue: {issue['message']}")
    print("✓ PASS: Missing Tax ID detected as HARD")


def test_e3_p4_other_country():
    """Test E3-P4: Country without specific requirements"""
    print("\n=== Test 4.6: E3-P4 - Other Country ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    invoice = create_minimal_invoice(country="GB")
    
    issues = _validate_policy_rules(db, invoice)
    
    p4_issues = [i for i in issues if i["code"] == "MISSING_COUNTRY_MANDATORY_FIELD"]
    assert len(p4_issues) == 0, "Country without specific requirements should not emit issue"
    print("✓ PASS: Other countries accepted without specific fields")


def test_multiple_policy_violations():
    """Test: Multiple policy violations aggregate correctly"""
    print("\n=== Test 5: Multiple Policy Violations ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    
    # Create invoice with multiple violations
    invoice = create_minimal_invoice(
        currency="XYZ",  # E3-P1: unsupported
        invoice_date=(today + datetime.timedelta(days=1)).isoformat(),  # E3-P2: future (HARD)
        total_amount=2_000_000.0,  # E3-P3: high amount (SOFT)
        country="IN"  # E3-P4: no GSTIN (HARD)
    )
    
    issues = _validate_policy_rules(db, invoice)
    
    print(f"Total issues: {len(issues)}")
    for issue in issues:
        print(f"  - {issue['code']} ({issue['severity']}): {issue['message']}")
    
    # Count by severity
    hard_issues = [i for i in issues if i["code"] != "VENDOR_NOT_FOUND" and i["severity"] == "HARD"]
    soft_issues = [i for i in issues if i["severity"] == "SOFT"]
    
    print(f"HARD issues: {len(hard_issues)}")
    print(f"SOFT issues: {len(soft_issues)}")
    
    assert len(hard_issues) >= 3, "Should have at least 3 HARD issues"
    assert len(soft_issues) >= 1, "Should have at least 1 SOFT issue"
    print("✓ PASS: Multiple violations aggregate correctly")


def test_valid_policy_compliant_invoice():
    """Test: Valid invoice compliant with all policies"""
    print("\n=== Test 6: Valid Policy-Compliant Invoice ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    
    invoice = create_minimal_invoice(
        currency="USD",
        invoice_date=(today - datetime.timedelta(days=10)).isoformat(),
        total_amount=50_000.0,
        country="US",
        tax_id="12-3456789"
    )
    
    issues = _validate_policy_rules(db, invoice)
    
    # Filter out vendor issue (if vendor not in DB)
    policy_issues = [i for i in issues if i["code"] != "VENDOR_NOT_FOUND"]
    
    print(f"Policy compliance issues: {len(policy_issues)}")
    assert len(policy_issues) == 0, "Valid invoice should have no policy issues"
    print("✓ PASS: Valid invoice accepted")


def test_backward_compatibility_vendor_check():
    """Test: Existing vendor check still works (backward compatibility)"""
    print("\n=== Test 7: Vendor Check (Backward Compatibility) ===")
    db = MockDB({})  # No vendors
    invoice = create_minimal_invoice(vendor_number="VND-NONEXISTENT")
    
    issues = _validate_policy_rules(db, invoice)
    
    vendor_issues = [i for i in issues if i["code"] == "VENDOR_NOT_FOUND"]
    assert len(vendor_issues) == 1, "Non-existent vendor should emit issue"
    issue = vendor_issues[0]
    assert issue["severity"] == "HARD", "Vendor issue should be HARD"
    print(f"Issue: {issue['message']}")
    print("✓ PASS: Vendor check still works")


def test_status_aggregation_with_policy():
    """Test: ValidationResult status correctly reflects policy issues"""
    print("\n=== Test 8: Status Aggregation with Policy Issues ===")
    db = MockDB({"VND-001": {"_id": "VND-001"}})
    today = datetime.datetime.utcnow().date()
    
    # Create invoice with HARD policy failure
    invoice = create_minimal_invoice(
        currency="XYZ"  # HARD
    )
    
    issues = _validate_policy_rules(db, invoice)
    result = build_validation_result(issues, datetime.datetime.utcnow().isoformat())
    
    print(f"Status: {result['status']}")
    print(f"HARD failures: {result['summary']['hard_failures']}")
    assert result["status"] == "FAIL", "HARD policy failure should result in FAIL status"
    assert result["summary"]["hard_failures"] > 0, "Should count HARD failures"
    print("✓ PASS: HARD policy failure produces FAIL status")
    
    # Create invoice with SOFT policy warning
    invoice_soft = create_minimal_invoice(
        total_amount=2_000_000.0  # SOFT
    )
    
    issues_soft = _validate_policy_rules(db, invoice_soft)
    result_soft = build_validation_result(issues_soft, datetime.datetime.utcnow().isoformat())
    
    print(f"\nStatus (SOFT only): {result_soft['status']}")
    print(f"SOFT warnings: {result_soft['summary']['soft_warnings']}")
    assert result_soft["status"] == "WARN", "SOFT policy warning should result in WARN status"
    print("✓ PASS: SOFT policy warning produces WARN status")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("STEP E3 - POLICY VALIDATION RULES TEST SUITE")
    print("="*80)
    
    tests = [
        # E3-P1: Currency
        test_e3_p1_currency_allowed,
        test_e3_p1_currency_unsupported,
        test_e3_p1_multiple_currencies,
        
        # E3-P2: Date window
        test_e3_p2_date_valid,
        test_e3_p2_date_future,
        test_e3_p2_date_old,
        test_e3_p2_date_boundary,
        
        # E3-P3: High amount
        test_e3_p3_high_amount_warn,
        test_e3_p3_high_amount_boundary,
        test_e3_p3_normal_amount,
        
        # E3-P4: Country-specific fields
        test_e3_p4_india_with_gstin,
        test_e3_p4_india_without_gstin,
        test_e3_p4_india_empty_gstin,
        test_e3_p4_us_with_tax_id,
        test_e3_p4_us_without_tax_id,
        test_e3_p4_other_country,
        
        # Integration tests
        test_multiple_policy_violations,
        test_valid_policy_compliant_invoice,
        test_backward_compatibility_vendor_check,
        test_status_aggregation_with_policy,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*80)
    
    if failed == 0:
        print("\n✓ ALL STEP E3 TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
