#!/usr/bin/env python3
"""
Test Step E1: Structural Validation Rule Expansion

Tests the 4 new STRUCTURAL validation rules:
- E1-S1: Empty or meaningless line description
- E1-S2: Duplicate or invalid line numbers
- E1-S3: Header total with no lines
- E1-S4: Zero or negative quantity (non-credit invoice)
"""

import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from app.agents.validation_domain import validate

print("\n" + "="*80)
print("TEST: Step E1 - Structural Validation Rule Expansion")
print("="*80)

# Mock database for POLICY rule testing (not needed for these tests but required by validate())
class MockDB:
    def get_collection(self, name):
        return MockCollection()

class MockCollection:
    def find_one(self, query):
        # Return a vendor for all queries (satisfies VENDOR_NOT_FOUND check)
        return {"_id": query.get("_id"), "name": "Test Vendor"}

mock_db = MockDB()

# ==============================================================================
# TEST E1-S1: Empty or Meaningless Line Description
# ==============================================================================
print("\n" + "-"*80)
print("TEST E1-S1: Empty or Meaningless Line Description")
print("-"*80)

# Test 1.1: Empty description
invoice_empty_desc = {
    "header": {
        "invoice_number": "INV001",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "",  # Empty
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_empty_desc)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "LINE_DESCRIPTION_EMPTY" for issue in result["issues"]), \
    "Expected LINE_DESCRIPTION_EMPTY issue"
assert any(issue["severity"] == "HARD" for issue in result["issues"] if issue["code"] == "LINE_DESCRIPTION_EMPTY"), \
    "LINE_DESCRIPTION_EMPTY should be HARD"
print("[OK] Empty description triggers LINE_DESCRIPTION_EMPTY (HARD)")

# Test 1.2: Whitespace-only description
invoice_whitespace_desc = {
    "header": {
        "invoice_number": "INV002",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "   ",  # Whitespace only
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_whitespace_desc)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "LINE_DESCRIPTION_EMPTY" for issue in result["issues"]), \
    "Expected LINE_DESCRIPTION_EMPTY issue"
print("[OK] Whitespace-only description triggers LINE_DESCRIPTION_EMPTY (HARD)")

# Test 1.3: Valid description (should not trigger)
invoice_valid_desc = {
    "header": {
        "invoice_number": "INV003",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Office Supplies",  # Valid
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_valid_desc)
# Should pass all structural checks (but might have issues from other rules)
has_desc_issue = any(issue["code"] == "LINE_DESCRIPTION_EMPTY" for issue in result["issues"])
assert not has_desc_issue, "Valid description should not trigger LINE_DESCRIPTION_EMPTY"
print("[OK] Valid description does not trigger issue")

# ==============================================================================
# TEST E1-S2: Duplicate or Invalid Line Numbers
# ==============================================================================
print("\n" + "-"*80)
print("TEST E1-S2: Duplicate or Invalid Line Numbers")
print("-"*80)

# Test 2.1: Duplicate line numbers
invoice_dup_lines = {
    "header": {
        "invoice_number": "INV004",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 2000.0
    },
    "lines": [
        {
            "line_number": 1,  # Duplicate
            "description": "Item 1",
            "quantity": 1,
            "line_amount": 1000.0
        },
        {
            "line_number": 1,  # Duplicate of above
            "description": "Item 2",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_dup_lines)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_NUMBER" for issue in result["issues"]), \
    "Expected INVALID_LINE_NUMBER issue for duplicates"
print("[OK] Duplicate line numbers trigger INVALID_LINE_NUMBER (HARD)")

# Test 2.2: Zero line number
invoice_zero_line = {
    "header": {
        "invoice_number": "INV005",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 0,  # Invalid: zero
            "description": "Item",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_zero_line)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_NUMBER" for issue in result["issues"]), \
    "Expected INVALID_LINE_NUMBER issue for zero"
print("[OK] Zero line number triggers INVALID_LINE_NUMBER (HARD)")

# Test 2.3: Negative line number
invoice_neg_line = {
    "header": {
        "invoice_number": "INV006",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": -1,  # Invalid: negative
            "description": "Item",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_neg_line)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_NUMBER" for issue in result["issues"]), \
    "Expected INVALID_LINE_NUMBER issue for negative"
print("[OK] Negative line number triggers INVALID_LINE_NUMBER (HARD)")

# Test 2.4: Non-numeric line number
invoice_nonnumeric_line = {
    "header": {
        "invoice_number": "INV007",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": "ABC",  # Invalid: non-numeric
            "description": "Item",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_nonnumeric_line)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_NUMBER" for issue in result["issues"]), \
    "Expected INVALID_LINE_NUMBER issue for non-numeric"
print("[OK] Non-numeric line number triggers INVALID_LINE_NUMBER (HARD)")

# Test 2.5: Valid line numbers
invoice_valid_lines = {
    "header": {
        "invoice_number": "INV008",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 2000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item 1",
            "quantity": 1,
            "line_amount": 1000.0
        },
        {
            "line_number": 2,
            "description": "Item 2",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_valid_lines)
has_line_num_issue = any(issue["code"] == "INVALID_LINE_NUMBER" for issue in result["issues"])
assert not has_line_num_issue, "Valid line numbers should not trigger issue"
print("[OK] Valid unique positive line numbers do not trigger issue")

# ==============================================================================
# TEST E1-S3: Header Total with No Lines
# ==============================================================================
print("\n" + "-"*80)
print("TEST E1-S3: Header Total with No Lines")
print("-"*80)

# Test 3.1: Total > 0 with empty lines
invoice_total_no_lines = {
    "header": {
        "invoice_number": "INV009",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": []  # Empty
}

result = validate(mock_db, invoice_total_no_lines)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "TOTAL_WITHOUT_LINES" for issue in result["issues"]), \
    "Expected TOTAL_WITHOUT_LINES issue"
print("[OK] Total > 0 with empty lines triggers TOTAL_WITHOUT_LINES (HARD)")

# Test 3.2: Total > 0 with no lines field
invoice_total_no_field = {
    "header": {
        "invoice_number": "INV010",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    }
    # No lines field at all
}

result = validate(mock_db, invoice_total_no_field)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "TOTAL_WITHOUT_LINES" for issue in result["issues"]), \
    "Expected TOTAL_WITHOUT_LINES issue when lines missing"
print("[OK] Total > 0 with missing lines field triggers TOTAL_WITHOUT_LINES (HARD)")

# Test 3.3: Total = 0 with no lines (should be OK)
invoice_zero_total_no_lines = {
    "header": {
        "invoice_number": "INV011",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 0.0
    },
    "lines": []
}

result = validate(mock_db, invoice_zero_total_no_lines)
has_total_issue = any(issue["code"] == "TOTAL_WITHOUT_LINES" for issue in result["issues"])
assert not has_total_issue, "Total = 0 with no lines should not trigger issue"
print("[OK] Total = 0 with empty lines does not trigger issue")

# Test 3.4: Total > 0 with at least one line (should be OK)
invoice_total_with_lines = {
    "header": {
        "invoice_number": "INV012",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item",
            "quantity": 1,
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_total_with_lines)
has_total_issue = any(issue["code"] == "TOTAL_WITHOUT_LINES" for issue in result["issues"])
assert not has_total_issue, "Total > 0 with lines should not trigger issue"
print("[OK] Total > 0 with at least one line does not trigger issue")

# ==============================================================================
# TEST E1-S4: Zero or Negative Quantity
# ==============================================================================
print("\n" + "-"*80)
print("TEST E1-S4: Zero or Negative Quantity (Non-Credit Invoice)")
print("-"*80)

# Test 4.1: Zero quantity
invoice_zero_qty = {
    "header": {
        "invoice_number": "INV013",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 0.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item",
            "quantity": 0,  # Invalid: zero
            "line_amount": 0.0
        }
    ]
}

result = validate(mock_db, invoice_zero_qty)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_QUANTITY" for issue in result["issues"]), \
    "Expected INVALID_LINE_QUANTITY issue for zero"
print("[OK] Zero quantity triggers INVALID_LINE_QUANTITY (HARD)")

# Test 4.2: Negative quantity
invoice_neg_qty = {
    "header": {
        "invoice_number": "INV014",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 0.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item",
            "quantity": -5,  # Invalid: negative
            "line_amount": -5000.0
        }
    ]
}

result = validate(mock_db, invoice_neg_qty)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_QUANTITY" for issue in result["issues"]), \
    "Expected INVALID_LINE_QUANTITY issue for negative"
print("[OK] Negative quantity triggers INVALID_LINE_QUANTITY (HARD)")

# Test 4.3: Non-numeric quantity
invoice_nonnumeric_qty = {
    "header": {
        "invoice_number": "INV015",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item",
            "quantity": "ABC",  # Invalid: non-numeric
            "line_amount": 1000.0
        }
    ]
}

result = validate(mock_db, invoice_nonnumeric_qty)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
assert any(issue["code"] == "INVALID_LINE_QUANTITY" for issue in result["issues"]), \
    "Expected INVALID_LINE_QUANTITY issue for non-numeric"
print("[OK] Non-numeric quantity triggers INVALID_LINE_QUANTITY (HARD)")

# Test 4.4: Valid positive quantity
invoice_valid_qty = {
    "header": {
        "invoice_number": "INV016",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 5000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Item 1",
            "quantity": 5,
            "line_amount": 5000.0
        }
    ]
}

result = validate(mock_db, invoice_valid_qty)
has_qty_issue = any(issue["code"] == "INVALID_LINE_QUANTITY" for issue in result["issues"])
assert not has_qty_issue, "Valid positive quantity should not trigger issue"
print("[OK] Valid positive quantity does not trigger issue")

# ==============================================================================
# TEST: Multiple Violations in Single Invoice
# ==============================================================================
print("\n" + "-"*80)
print("TEST: Multiple E1 Violations in Single Invoice")
print("-"*80)

invoice_multiple_violations = {
    "header": {
        "invoice_number": "INV017",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 1000.0  # Total > 0 but only one line will be valid
    },
    "lines": [
        {
            "line_number": 1,
            "description": "",  # E1-S1: Empty
            "quantity": 0,  # E1-S4: Zero quantity
            "line_amount": 500.0
        },
        {
            "line_number": 1,  # E1-S2: Duplicate
            "description": "Item",
            "quantity": 1,
            "line_amount": 500.0
        }
    ]
}

result = validate(mock_db, invoice_multiple_violations)
assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"

# Count different issue types
desc_issues = [i for i in result["issues"] if i["code"] == "LINE_DESCRIPTION_EMPTY"]
line_num_issues = [i for i in result["issues"] if i["code"] == "INVALID_LINE_NUMBER"]
qty_issues = [i for i in result["issues"] if i["code"] == "INVALID_LINE_QUANTITY"]

assert len(desc_issues) > 0, "Should have at least one description issue"
assert len(line_num_issues) > 0, "Should have at least one line number issue"
assert len(qty_issues) > 0, "Should have at least one quantity issue"

print(f"[OK] Multiple violations detected: {len(desc_issues)} description, {len(line_num_issues)} line number, {len(qty_issues)} quantity issues")

# ==============================================================================
# TEST: Valid Invoice (All E1 Rules Pass)
# ==============================================================================
print("\n" + "-"*80)
print("TEST: Valid Invoice (All E1 Rules Pass)")
print("-"*80)

invoice_valid_e1 = {
    "header": {
        "invoice_number": "INV018",
        "invoice_date": "2024-01-01",
        "vendor_number": "VENDOR1",
        "currency": "USD",
        "total_amount": 3000.0
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Office Supplies",
            "quantity": 2,
            "line_amount": 1500.0
        },
        {
            "line_number": 2,
            "description": "Equipment",
            "quantity": 1.5,
            "line_amount": 1500.0
        }
    ]
}

result = validate(mock_db, invoice_valid_e1)

# Check no E1 violations
e1_issues = [i for i in result["issues"] if i["code"] in [
    "LINE_DESCRIPTION_EMPTY",
    "INVALID_LINE_NUMBER",
    "TOTAL_WITHOUT_LINES",
    "INVALID_LINE_QUANTITY"
]]

assert len(e1_issues) == 0, f"Valid invoice should not trigger any E1 issues, but got: {e1_issues}"
print("[OK] Valid invoice passes all E1 structural rules")

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "="*80)
print("ALL STEP E1 TESTS PASSED")
print("="*80)
print("""
[OK] E1-S1: Empty line description detection works
[OK] E1-S2: Invalid/duplicate line number detection works
[OK] E1-S3: Total without lines detection works
[OK] E1-S4: Invalid quantity detection works
[OK] Multiple violations aggregated correctly
[OK] Valid invoices pass all E1 rules

Step E1: STRUCTURAL validation rules successfully implemented.
""")
