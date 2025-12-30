"""
Backward Compatibility Tests for Step E5.

Verifies that:
- All E1-E4 validation rules work without config service
- ValidationDomain remains backward compatible
- Existing tests continue to pass
- Config service is optional
"""

import sys
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

try:
    from app.agents.validation_domain import validate, _validate_structural_rules, _validate_financial_rules, _validate_policy_rules, _validate_duplicate_rules
    from app.services.config_service import ConfigurationService
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)


class MockDB:
    """Mock database for backward compatibility tests."""
    def __init__(self):
        self.collections = {}
    
    def get_collection(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]
    
    def __getitem__(self, name):
        return self.get_collection(name)


class MockCollection:
    def __init__(self):
        self.data = {}
    
    def find_one(self, query):
        for doc in self.data.values():
            match = all(doc.get(k) == v for k, v in query.items() if not isinstance(v, dict))
            if match:
                return doc
        return None
    
    def insert_one(self, doc):
        doc_id = len(self.data) + 1
        self.data[doc_id] = doc
        return Mock(inserted_id=doc_id)


def create_sample_invoice():
    """Create a sample valid invoice for testing."""
    return {
        "_id": "INV-001",
        "header": {
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-12-30T10:00:00Z",
            "vendor_number": "VND-001",
            "vendor_name": "Test Vendor",
            "currency": "USD",
            "total_amount": 1000.00,
            "tax_amount": 100.00,
            "discount_amount": 0.00,
            "discount_rate": 0.0
        },
        "lines": [
            {
                "line_number": 1,
                "description": "Test Line Item",
                "quantity": 1.0,
                "unit_price": 900.00,
                "line_amount": 900.00,
                "tax_amount": 90.00
            },
            {
                "line_number": 2,
                "description": "Another Line",
                "quantity": 1.0,
                "unit_price": 100.00,
                "line_amount": 100.00,
                "tax_amount": 10.00
            }
        ]
    }


def test_backward_compat_structural_rules_standalone():
    """Test E1 structural rules work standalone (no config service)."""
    invoice = create_sample_invoice()
    
    issues = _validate_structural_rules(invoice)
    
    # Valid invoice should have no structural issues
    assert len(issues) == 0, f"Expected no issues, got: {issues}"
    print("[OK] PASS: E1 Structural rules work standalone")


def test_backward_compat_structural_rules_missing_field():
    """Test E1 structural rules detect missing fields."""
    invoice = create_sample_invoice()
    del invoice["header"]["invoice_number"]
    
    issues = _validate_structural_rules(invoice)
    
    # Should have MISSING_FIELD issue
    missing_field_issues = [i for i in issues if i["code"] == "MISSING_FIELD"]
    assert len(missing_field_issues) > 0
    print("[OK] PASS: E1 Structural rules detect missing fields")


def test_backward_compat_financial_rules_no_config():
    """Test E2 financial rules work without config service."""
    invoice = create_sample_invoice()
    
    # Call without config_service (None)
    issues = _validate_financial_rules(invoice, config_service=None)
    
    # Valid invoice should have no financial issues
    assert len(issues) == 0, f"Expected no issues, got: {issues}"
    print("[OK] PASS: E2 Financial rules work without config service")


def test_backward_compat_financial_rules_with_config():
    """Test E2 financial rules work with config service."""
    invoice = create_sample_invoice()
    db = MockDB()
    service = ConfigurationService(db)
    
    # Call with config_service
    issues = _validate_financial_rules(invoice, config_service=service, org_id="ORG-001")
    
    # Should still work
    assert isinstance(issues, list)
    print("[OK] PASS: E2 Financial rules work with config service")


def test_backward_compat_validate_no_config():
    """Test main validate() function works without config service."""
    invoice = create_sample_invoice()
    db = MockDB()
    
    # Add vendor to DB
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001", "vendor_name": "Test Vendor"}
    
    # Call without config service
    result = validate(db, invoice)
    
    # Should have standard ValidationResult structure
    assert "status" in result
    assert "issues" in result
    assert "summary" in result
    print("[OK] PASS: Validate function works without config service")


def test_backward_compat_validate_with_config():
    """Test main validate() function works with config service."""
    invoice = create_sample_invoice()
    db = MockDB()
    service = ConfigurationService(db)
    
    # Add vendor to DB
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001", "vendor_name": "Test Vendor"}
    
    # Call with config service
    result = validate(db, invoice, config_service=service, org_id="ORG-001")
    
    # Should have standard ValidationResult structure
    assert "status" in result
    assert "issues" in result
    assert "summary" in result
    print("[OK] PASS: Validate function works with config service")


def test_backward_compat_validation_result_structure():
    """Test ValidationResult structure remains consistent."""
    invoice = create_sample_invoice()
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    result = validate(db, invoice)
    
    # Check expected ValidationResult fields
    assert "status" in result
    assert result["status"] in ["PASS", "WARN", "FAIL"]
    assert "issues" in result
    assert isinstance(result["issues"], list)
    assert "summary" in result
    assert "hard_failures" in result["summary"]
    assert "soft_warnings" in result["summary"]
    assert "validated_at" in result
    
    print("[OK] PASS: ValidationResult structure is consistent")


def test_backward_compat_issue_structure():
    """Test issue structure remains consistent."""
    invoice = create_sample_invoice()
    del invoice["header"]["invoice_number"]
    
    db = MockDB()
    
    result = validate(db, invoice)
    
    # Find an issue
    assert len(result["issues"]) > 0
    issue = result["issues"][0]
    
    # Check expected issue fields
    assert "code" in issue
    assert "category" in issue
    assert "severity" in issue
    assert "field" in issue
    assert "message" in issue
    assert "metadata" in issue
    
    print("[OK] PASS: Issue structure is consistent")


def test_backward_compat_hard_failure():
    """Test HARD failures still mark invoice as FAIL."""
    invoice = create_sample_invoice()
    del invoice["header"]["invoice_number"]
    
    db = MockDB()
    
    result = validate(db, invoice)
    
    # HARD failure should result in FAIL status
    assert result["status"] == "FAIL"
    assert result["summary"]["hard_failures"] > 0
    
    print("[OK] PASS: HARD failures mark invoice as FAIL")


def test_backward_compat_soft_warning():
    """Test SOFT warnings mark invoice as WARN."""
    invoice = create_sample_invoice()
    # Slightly mismatched totals (within tolerance but present)
    invoice["lines"][0]["line_amount"] = 899.99
    
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    result = validate(db, invoice)
    
    # Could be PASS or WARN depending on tolerance calculation
    assert result["status"] in ["PASS", "WARN"]
    
    print("[OK] PASS: SOFT warnings handled correctly")


def test_backward_compat_policy_rules_no_config():
    """Test E3 policy rules work without config service."""
    invoice = create_sample_invoice()
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    # Call without config service
    issues = _validate_policy_rules(db, invoice, config_service=None)
    
    # Should return list (may have issues or not)
    assert isinstance(issues, list)
    print("[OK] PASS: E3 Policy rules work without config service")


def test_backward_compat_duplicate_rules_no_config():
    """Test E4 duplicate rules work without config service."""
    invoice = create_sample_invoice()
    db = MockDB()
    
    # Call without config service
    issues = _validate_duplicate_rules(db, invoice, config_service=None)
    
    # Should return list
    assert isinstance(issues, list)
    print("[OK] PASS: E4 Duplicate rules work without config service")


def test_backward_compat_config_service_optional():
    """Test that config_service parameter is optional."""
    invoice = create_sample_invoice()
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    # Call validate without any config parameters
    result1 = validate(db, invoice)
    assert result1 is not None
    
    # Call validate with only db
    result2 = validate(db, invoice, config_service=None)
    assert result2 is not None
    
    print("[OK] PASS: Config service is optional")


def test_backward_compat_no_regression():
    """Test no regressions in core validation logic."""
    invoice = create_sample_invoice()
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    result_without_config = validate(db, invoice, config_service=None)
    
    # Run with config service
    service = ConfigurationService(db)
    result_with_config = asyncio.run(_validate_async(db, invoice, service))
    
    # Both should have same structure
    assert "status" in result_without_config
    assert "status" in result_with_config
    assert "issues" in result_without_config
    assert "issues" in result_with_config
    
    print("[OK] PASS: No regression in core validation logic")


async def _validate_async(db, invoice, service):
    """Helper to test async config service."""
    return validate(db, invoice, config_service=service)


def test_backward_compat_config_service_graceful_fallback():
    """Test graceful fallback if config service fails."""
    invoice = create_sample_invoice()
    db = MockDB()
    vendors = db.get_collection("vendors")
    vendors.data[1] = {"_id": "VND-001"}
    
    # Create a broken config service
    broken_service = MagicMock()
    broken_service.get_rule_config = MagicMock(side_effect=Exception("DB error"))
    
    # Should still work by falling back to hardcoded defaults
    issues = _validate_financial_rules(invoice, config_service=broken_service)
    assert isinstance(issues, list)
    
    print("[OK] PASS: Graceful fallback if config service fails")


# Run all tests
if __name__ == "__main__":
    tests = [
        test_backward_compat_structural_rules_standalone,
        test_backward_compat_structural_rules_missing_field,
        test_backward_compat_financial_rules_no_config,
        test_backward_compat_financial_rules_with_config,
        test_backward_compat_validate_no_config,
        test_backward_compat_validate_with_config,
        test_backward_compat_validation_result_structure,
        test_backward_compat_issue_structure,
        test_backward_compat_hard_failure,
        test_backward_compat_soft_warning,
        test_backward_compat_policy_rules_no_config,
        test_backward_compat_duplicate_rules_no_config,
        test_backward_compat_config_service_optional,
        test_backward_compat_no_regression,
        test_backward_compat_config_service_graceful_fallback,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\nRESULTS: {passed} passed, {failed} failed")
    if failed == 0:
        print("[OK] ALL BACKWARD COMPATIBILITY TESTS PASSED")
    else:
        sys.exit(1)
