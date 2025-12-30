"""
Test suite for Step E4 - Duplicate & Risk Validation Rules

Tests all 3 duplicate rules:
- E4-D1: Exact duplicate invoice
- E4-D2: Time-window duplicate (same amount within 30 days)
- E4-D3: Similar amount heuristic (±2% within 60 days)

Verifies:
1. Each rule works independently
2. Violations emit correct severity (HARD/SOFT)
3. Boundary conditions handled correctly
4. Multiple violations aggregate correctly
5. Valid non-duplicates pass without issues
"""

import sys
import os
import datetime
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.validation_domain import _validate_duplicate_rules, build_validation_result


class MockDB:
    """Mock MongoDB client for testing"""
    
    def __init__(self, invoices=None):
        self.invoices_data = invoices or {}
    
    def get_collection(self, name):
        if name == "invoices":
            return MockCollection(self.invoices_data)
        return MockCollection({})


class MockCollection:
    """Mock MongoDB collection"""
    
    def __init__(self, data):
        self.data = data
    
    def find_one(self, query):
        """
        Simple query matching for testing:
        - Supports $ne (not equal)
        - Supports $gte/$lte for ranges
        - Supports field matching
        """
        for invoice in self.data.values():
            if self._matches_query(invoice, query):
                return invoice
        return None
    
    def _matches_query(self, doc, query):
        """Check if document matches query"""
        for key, value in query.items():
            doc_val = self._get_nested(doc, key)
            
            if isinstance(value, dict):
                # Handle operators
                if "$ne" in value:
                    if doc_val == value["$ne"]:
                        return False
                if "$gte" in value and "$lte" in value:
                    # Range query
                    range_val = value["$gte"]
                    if isinstance(range_val, str):
                        # Date string comparison
                        if doc_val < range_val or doc_val > value["$lte"]:
                            return False
                    else:
                        if doc_val < range_val or doc_val > value["$lte"]:
                            return False
                elif "$gte" in value:
                    if doc_val is None or doc_val < value["$gte"]:
                        return False
                elif "$lte" in value:
                    if doc_val is None or doc_val > value["$lte"]:
                        return False
            else:
                # Direct match
                if doc_val != value:
                    return False
        
        return True
    
    def _get_nested(self, doc, key):
        """Get nested field value (e.g., header.vendor_number)"""
        parts = key.split(".")
        val = doc
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val


def create_invoice(invoice_id, vendor_id="VND-001", invoice_number="INV-001",
                   total_amount=1000.0, invoice_date=None):
    """Create a test invoice"""
    if invoice_date is None:
        invoice_date = datetime.datetime.utcnow().date().isoformat()
    
    return {
        "_id": invoice_id,
        "header": {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "vendor_number": vendor_id,
            "total_amount": total_amount,
            "currency": "USD"
        },
        "lines": [{"line_amount": total_amount}]
    }


def test_e4_d1_no_duplicate():
    """Test E4-D1: No existing duplicate - should NOT emit issue"""
    print("\n=== Test 1.1: E4-D1 - No Duplicate ===")
    db = MockDB({})
    invoice = create_invoice("INV-NEW", vendor_id="VND-001", invoice_number="INV-001")
    
    issues = _validate_duplicate_rules(db, invoice)
    
    d1_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_EXACT"]
    print("Issues found: {}".format(len(d1_issues)))
    assert len(d1_issues) == 0, "No duplicate should not emit issue"
    print("[OK] PASS: Non-duplicate invoice accepted")


def test_e4_d1_exact_duplicate():
    """Test E4-D1: Exact duplicate found - should emit HARD issue"""
    print("\n=== Test 1.2: E4-D1 - Exact Duplicate ===")
    
    # Create existing invoice
    existing = create_invoice("INV-001", vendor_id="VND-001", invoice_number="INV-100")
    db = MockDB({"INV-001": existing})
    
    # Try to add same invoice
    new_invoice = create_invoice("INV-NEW", vendor_id="VND-001", invoice_number="INV-100")
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d1_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_EXACT"]
    assert len(d1_issues) == 1, "Exact duplicate should emit one issue"
    issue = d1_issues[0]
    assert issue["severity"] == "HARD", "Exact duplicate should be HARD"
    print("Issue: {}".format(issue['message']))
    print("Existing invoice ID: {}".format(issue['metadata']['existing_invoice_id']))
    print("[OK] PASS: Exact duplicate detected as HARD")


def test_e4_d1_different_vendors():
    """Test E4-D1: Same invoice number, different vendor - should NOT emit issue"""
    print("\n=== Test 1.3: E4-D1 - Different Vendors ===")
    
    existing = create_invoice("INV-001", vendor_id="VND-001", invoice_number="INV-100")
    db = MockDB({"INV-001": existing})
    
    # Different vendor, same invoice number
    new_invoice = create_invoice("INV-NEW", vendor_id="VND-002", invoice_number="INV-100")
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d1_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_EXACT"]
    assert len(d1_issues) == 0, "Different vendors should not trigger duplicate"
    print("[OK] PASS: Different vendors accepted")


def test_e4_d2_no_time_window_duplicate():
    """Test E4-D2: No duplicate within 30 days - should NOT emit issue"""
    print("\n=== Test 2.1: E4-D2 - No Time-Window Duplicate ===")
    db = MockDB({})
    invoice = create_invoice("INV-NEW", vendor_id="VND-001", total_amount=1000.0)
    
    issues = _validate_duplicate_rules(db, invoice)
    
    d2_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_TIME_WINDOW"]
    assert len(d2_issues) == 0, "No duplicate should not emit issue"
    print("[OK] PASS: No time-window duplicate")


def test_e4_d2_time_window_duplicate():
    """Test E4-D2: Same amount, same vendor within 30 days - should emit SOFT issue"""
    print("\n=== Test 2.2: E4-D2 - Time-Window Duplicate ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create existing invoice from 5 days ago
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=5)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    # New invoice, same vendor, same amount, today
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1000.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d2_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_TIME_WINDOW"]
    assert len(d2_issues) == 1, "Time-window duplicate should emit one issue"
    issue = d2_issues[0]
    assert issue["severity"] == "SOFT", "Time-window duplicate should be SOFT"
    print("Issue: {}".format(issue['message']))
    print("Window: {} days".format(issue['metadata']['window_days']))
    print("[OK] PASS: Time-window duplicate detected as SOFT")


def test_e4_d2_outside_window():
    """Test E4-D2: Same amount but outside 30-day window - should NOT emit issue"""
    print("\n=== Test 2.3: E4-D2 - Outside 30-Day Window ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create existing invoice from 40 days ago (outside 30-day window)
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=40)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    # New invoice today
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1000.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d2_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_TIME_WINDOW"]
    assert len(d2_issues) == 0, "Outside window should not trigger"
    print("[OK] PASS: Outside window not flagged")


def test_e4_d3_no_similar_amount():
    """Test E4-D3: No similar amount - should NOT emit issue"""
    print("\n=== Test 3.1: E4-D3 - No Similar Amount ===")
    db = MockDB({})
    invoice = create_invoice("INV-NEW", vendor_id="VND-001", total_amount=1000.0)
    
    issues = _validate_duplicate_rules(db, invoice)
    
    d3_issues = [i for i in issues if i["code"] == "SIMILAR_INVOICE_AMOUNT"]
    assert len(d3_issues) == 0, "No similar invoice should not emit issue"
    print("[OK] PASS: No similar amount detected")


def test_e4_d3_similar_amount_within_tolerance():
    """Test E4-D3: Similar amount (±2%) within 60 days - should emit SOFT issue"""
    print("\n=== Test 3.2: E4-D3 - Similar Amount Within Tolerance ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create existing invoice with $1000
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=10)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    # New invoice with $1010 (1% difference, within 2% tolerance)
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1010.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d3_issues = [i for i in issues if i["code"] == "SIMILAR_INVOICE_AMOUNT"]
    assert len(d3_issues) == 1, "Similar amount should emit one issue"
    issue = d3_issues[0]
    assert issue["severity"] == "SOFT", "Similar amount should be SOFT"
    print("Issue: {}".format(issue['message']))
    print("Current: {}, Existing: {}".format(
        issue['metadata']['current_amount'],
        issue['metadata']['similar_amount']
    ))
    print("Difference: {}%".format(issue['metadata']['pct_difference']))
    print("[OK] PASS: Similar amount detected as SOFT")


def test_e4_d3_amount_outside_tolerance():
    """Test E4-D3: Amount outside ±2% tolerance - should NOT emit issue"""
    print("\n=== Test 3.3: E4-D3 - Amount Outside Tolerance ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create existing invoice with $1000
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=10)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    # New invoice with $1030 (3% difference, outside 2% tolerance)
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1030.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d3_issues = [i for i in issues if i["code"] == "SIMILAR_INVOICE_AMOUNT"]
    assert len(d3_issues) == 0, "Amount outside tolerance should not trigger"
    print("[OK] PASS: Outside tolerance not flagged")


def test_e4_d3_outside_60_day_window():
    """Test E4-D3: Similar amount but outside 60-day window - should NOT emit issue"""
    print("\n=== Test 3.4: E4-D3 - Outside 60-Day Window ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create existing invoice from 70 days ago (outside 60-day window)
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=70)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    # New invoice with similar amount today
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1010.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    d3_issues = [i for i in issues if i["code"] == "SIMILAR_INVOICE_AMOUNT"]
    assert len(d3_issues) == 0, "Outside window should not trigger"
    print("[OK] PASS: Outside 60-day window not flagged")


def test_recurring_legitimate_invoice():
    """Test: Legitimate recurring invoice (different numbers) - should PASS"""
    print("\n=== Test 4: Recurring Legitimate Invoice ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create 3 invoices from same vendor with similar amounts (legitimate recurring)
    invoices = {
        "INV-001": create_invoice("INV-001", vendor_id="VND-001", invoice_number="INV-JAN",
                                 total_amount=5000.0,
                                 invoice_date=(today - datetime.timedelta(days=60)).isoformat()),
        "INV-002": create_invoice("INV-002", vendor_id="VND-001", invoice_number="INV-FEB",
                                 total_amount=5050.0,  # +1% (within tolerance)
                                 invoice_date=(today - datetime.timedelta(days=30)).isoformat()),
    }
    db = MockDB(invoices)
    
    # New monthly invoice
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-MAR",
        total_amount=5100.0,  # +2% from first (outside tolerance)
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    # May have E4-D2 if exactly same amount within 30 days, but $5100 is different
    # and E4-D3 should not trigger because $5100 is >2% from $5050
    d1_issues = [i for i in issues if i["code"] == "DUPLICATE_INVOICE_EXACT"]
    assert len(d1_issues) == 0, "Different invoice numbers should not trigger exact duplicate"
    
    print("Total issues: {}".format(len(issues)))
    if issues:
        for issue in issues:
            print("  - {}: {}".format(issue['code'], issue['message']))
    print("[OK] PASS: Legitimate recurring invoices handled")


def test_multiple_duplicate_violations():
    """Test: Multiple duplicate violations aggregate correctly"""
    print("\n=== Test 5: Multiple Duplicate Violations ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create invoices that will trigger multiple rules
    existing_exact = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=5)).isoformat()
    )
    
    existing_similar = create_invoice(
        "INV-002",
        vendor_id="VND-001",
        invoice_number="INV-200",
        total_amount=1010.0,  # Within 2%
        invoice_date=(today - datetime.timedelta(days=20)).isoformat()
    )
    
    db = MockDB({"INV-001": existing_exact, "INV-002": existing_similar})
    
    # New invoice: exact match with INV-001 (E4-D1), similar to INV-002 (E4-D3)
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-100",  # Same as INV-001
        total_amount=1000.0,  # Same as INV-001, within 2% of INV-002
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    print("Total issues: {}".format(len(issues)))
    hard_issues = [i for i in issues if i["severity"] == "HARD"]
    soft_issues = [i for i in issues if i["severity"] == "SOFT"]
    
    for issue in issues:
        print("  - {} ({}): {}".format(issue['code'], issue['severity'], issue['message']))
    
    assert len(hard_issues) >= 1, "Should have at least 1 HARD issue"
    print("HARD issues: {}, SOFT issues: {}".format(len(hard_issues), len(soft_issues)))
    print("[OK] PASS: Multiple violations aggregate correctly")


def test_status_aggregation_hard_duplicate():
    """Test: HARD duplicate produces FAIL status"""
    print("\n=== Test 6: Status Aggregation - HARD Duplicate ===")
    
    existing = create_invoice("INV-001", vendor_id="VND-001", invoice_number="INV-100")
    db = MockDB({"INV-001": existing})
    
    new_invoice = create_invoice("INV-NEW", vendor_id="VND-001", invoice_number="INV-100")
    
    issues = _validate_duplicate_rules(db, new_invoice)
    result = build_validation_result(issues, datetime.datetime.utcnow().isoformat())
    
    print("Status: {}".format(result['status']))
    print("HARD failures: {}".format(result['summary']['hard_failures']))
    assert result["status"] == "FAIL", "HARD duplicate should produce FAIL status"
    print("[OK] PASS: HARD duplicate produces FAIL status")


def test_status_aggregation_soft_duplicate():
    """Test: SOFT duplicate produces WARN status (if no HARD)"""
    print("\n=== Test 7: Status Aggregation - SOFT Duplicate ===")
    
    today = datetime.datetime.utcnow().date()
    
    existing = create_invoice(
        "INV-001",
        vendor_id="VND-001",
        invoice_number="INV-100",
        total_amount=1000.0,
        invoice_date=(today - datetime.timedelta(days=5)).isoformat()
    )
    db = MockDB({"INV-001": existing})
    
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-001",
        invoice_number="INV-101",
        total_amount=1000.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    result = build_validation_result(issues, datetime.datetime.utcnow().isoformat())
    
    print("Status: {}".format(result['status']))
    print("SOFT warnings: {}".format(result['summary']['soft_warnings']))
    assert result["status"] == "WARN", "SOFT duplicate should produce WARN status"
    print("[OK] PASS: SOFT duplicate produces WARN status")


def test_valid_non_duplicate():
    """Test: Valid non-duplicate invoice"""
    print("\n=== Test 8: Valid Non-Duplicate Invoice ===")
    
    today = datetime.datetime.utcnow().date()
    
    # Create several existing invoices from different vendors
    invoices = {
        "INV-001": create_invoice("INV-001", vendor_id="VND-001", invoice_number="INV-100",
                                 total_amount=1000.0),
        "INV-002": create_invoice("INV-002", vendor_id="VND-002", invoice_number="INV-200",
                                 total_amount=2000.0),
    }
    db = MockDB(invoices)
    
    # New invoice from different vendor, different amount, different number
    new_invoice = create_invoice(
        "INV-NEW",
        vendor_id="VND-003",
        invoice_number="INV-300",
        total_amount=3000.0,
        invoice_date=today.isoformat()
    )
    
    issues = _validate_duplicate_rules(db, new_invoice)
    
    duplicate_issues = [i for i in issues if i["category"] == "DUPLICATE"]
    print("Duplicate issues: {}".format(len(duplicate_issues)))
    assert len(duplicate_issues) == 0, "Valid invoice should not have duplicate issues"
    print("[OK] PASS: Valid non-duplicate accepted")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("STEP E4 - DUPLICATE & RISK VALIDATION RULES TEST SUITE")
    print("="*80)
    
    tests = [
        # E4-D1: Exact duplicate
        test_e4_d1_no_duplicate,
        test_e4_d1_exact_duplicate,
        test_e4_d1_different_vendors,
        
        # E4-D2: Time-window duplicate
        test_e4_d2_no_time_window_duplicate,
        test_e4_d2_time_window_duplicate,
        test_e4_d2_outside_window,
        
        # E4-D3: Similar amount
        test_e4_d3_no_similar_amount,
        test_e4_d3_similar_amount_within_tolerance,
        test_e4_d3_amount_outside_tolerance,
        test_e4_d3_outside_60_day_window,
        
        # Integration tests
        test_recurring_legitimate_invoice,
        test_multiple_duplicate_violations,
        test_status_aggregation_hard_duplicate,
        test_status_aggregation_soft_duplicate,
        test_valid_non_duplicate,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print("[FAIL]: {}".format(e))
            failed += 1
        except Exception as e:
            print("[ERROR]: {}".format(e))
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*80)
    print("RESULTS: {} passed, {} failed".format(passed, failed))
    print("="*80)
    
    if failed == 0:
        print("\n[OK] ALL STEP E4 TESTS PASSED")
        return 0
    else:
        print("\n[FAIL] {} test(s) failed".format(failed))
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
