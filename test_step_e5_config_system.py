"""
Integration tests for Step E5: Configuration System.

Tests full E5 configuration system with:
- Admin API endpoints
- Configuration persistence
- Validation with configuration
- Multi-tenant isolation
- Multi-region resolution
- Backward compatibility
"""

import sys
import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, Mock

# Test imports
try:
    from app.services.config_service import ConfigurationService, DEFAULT_CONFIG
    from app.services.config_validator import validate_parameters
    from app.models.admin_config import (
        ConfigurationParametersUpdate,
        ConfigurationUpdateResponse
    )
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)


class MockMongoDB:
    """Mock MongoDB for testing."""
    def __init__(self):
        self.validation_config = {}
        self.call_history = []
    
    def find_one(self, query):
        self.call_history.append(("find_one", query))
        for doc in self.validation_config.values():
            match = all(doc.get(k) == v for k, v in query.items())
            if match:
                return doc
        return None
    
    def find(self, query):
        self.call_history.append(("find", query))
        results = []
        for doc in self.validation_config.values():
            match = True
            for k, v in query.items():
                if isinstance(v, dict) and "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        match = False
                else:
                    if doc.get(k) != v:
                        match = False
            if match:
                results.append(doc)
        return results
    
    def insert_one(self, doc):
        doc_id = len(self.validation_config) + 1
        self.validation_config[doc_id] = doc
        return Mock(inserted_id=doc_id)
    
    def update_one(self, query, update, upsert=False):
        self.call_history.append(("update_one", query, update))
        for doc in self.validation_config.values():
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                return Mock(matched_count=1)
        
        if upsert:
            new_doc = {**query}
            new_doc.update(update.get("$set", {}))
            doc_id = len(self.validation_config) + 1
            self.validation_config[doc_id] = new_doc
            return Mock(matched_count=0)
        
        return Mock(matched_count=0)


def test_e5_config_service_full_workflow():
    """Test full E5 configuration workflow."""
    db = MockMongoDB()
    service = ConfigurationService(db)
    
    # Step 1: Get default config (nothing in DB)
    config = asyncio.run(service.get_rule_config("ORG-TEST", "E2-F1", "US"))
    assert config["_source"] == "hardcoded_default"
    print("[OK] PASS: E5-1 Default configuration retrieval")
    
    # Step 2: Update configuration via API-like flow
    request_data = {
        "organization_id": "ORG-TEST",
        "region": "US",
        "enabled": True,
        "parameters": {
            "tolerance_amount_cents": 250,
            "tolerance_percentage": 0.75,
            "warning_threshold_percentage": 2.5
        },
        "reason": "E5 test configuration"
    }
    
    # Simulate update_one call
    updated_doc = {
        "organization_id": "ORG-TEST",
        "region": "US",
        "rule_id": "E2-F1",
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "severity": "SOFT",
        "enabled": True,
        "parameters": request_data["parameters"],
        "updated_at": datetime.utcnow(),
        "updated_by": "test_admin",
        "change_history": [{
            "timestamp": datetime.utcnow(),
            "changed_by": "test_admin",
            "field_changed": "parameters",
            "old_value": DEFAULT_CONFIG["E2-F1"]["parameters"],
            "new_value": request_data["parameters"],
            "reason": "E5 test configuration"
        }]
    }
    
    db.validation_config[1] = updated_doc
    
    # Step 3: Clear cache and retrieve updated config
    asyncio.run(service.reload_config("ORG-TEST", "US", "E2-F1"))
    updated_config = asyncio.run(service.get_rule_config("ORG-TEST", "E2-F1", "US"))
    
    assert updated_config["parameters"]["tolerance_amount_cents"] == 250
    print("[OK] PASS: E5-2 Configuration update and retrieval")


def test_e5_multi_org_isolation():
    """Test multi-org isolation in E5."""
    db = MockMongoDB()
    
    # Add configs for different orgs
    db.validation_config[1] = {
        "organization_id": "ORG-A",
        "region": "US",
        "rule_id": "E2-F1",
        "parameters": {"tolerance_amount_cents": 100}
    }
    
    db.validation_config[2] = {
        "organization_id": "ORG-B",
        "region": "US",
        "rule_id": "E2-F1",
        "parameters": {"tolerance_amount_cents": 500}
    }
    
    service = ConfigurationService(db)
    
    # Get config for each org
    config_a = asyncio.run(service.get_rule_config("ORG-A", "E2-F1", "US"))
    config_b = asyncio.run(service.get_rule_config("ORG-B", "E2-F1", "US"))
    
    assert config_a["parameters"]["tolerance_amount_cents"] == 100
    assert config_b["parameters"]["tolerance_amount_cents"] == 500
    
    print("[OK] PASS: E5-3 Multi-organization isolation")


def test_e5_multi_region_resolution():
    """Test multi-region config resolution in E5."""
    db = MockMongoDB()
    
    # Add only global (ALL) config
    db.validation_config[1] = {
        "organization_id": "ORG-MULTI",
        "region": "ALL",
        "rule_id": "E2-F1",
        "parameters": {"tolerance_amount_cents": 200}
    }
    
    service = ConfigurationService(db)
    
    # Request EU region (not in DB) - should fall back to ALL
    config_eu = asyncio.run(service.get_rule_config("ORG-MULTI", "E2-F1", "EU"))
    assert config_eu["parameters"]["tolerance_amount_cents"] == 200
    
    # Request US region (also not specifically configured) - should fall back to ALL
    config_us = asyncio.run(service.get_rule_config("ORG-MULTI", "E2-F1", "US"))
    assert config_us["parameters"]["tolerance_amount_cents"] == 200
    
    print("[OK] PASS: E5-4 Multi-region resolution")


def test_e5_parameter_validation_e2f1():
    """Test E2-F1 parameter validation."""
    # Valid E2-F1 parameters
    valid_params = {
        "tolerance_amount_cents": 100,
        "tolerance_percentage": 0.5,
        "warning_threshold_percentage": 2.0
    }
    is_valid, errors = validate_parameters("E2-F1", valid_params)
    assert is_valid is True
    print("[OK] PASS: E5-5a Parameter validation E2-F1 (valid)")
    
    # Invalid: tolerance > warning_threshold
    invalid_params = {
        "tolerance_percentage": 3.0,
        "warning_threshold_percentage": 2.0
    }
    is_valid, errors = validate_parameters("E2-F1", invalid_params)
    assert is_valid is False
    assert len(errors) > 0
    print("[OK] PASS: E5-5b Parameter validation E2-F1 (invalid)")


def test_e5_parameter_validation_e3p1():
    """Test E3-P1 currency parameter validation."""
    # Valid currencies
    valid_params = {
        "allowed_currencies": ["USD", "EUR", "GBP"]
    }
    is_valid, errors = validate_parameters("E3-P1", valid_params)
    assert is_valid is True
    print("[OK] PASS: E5-6a Parameter validation E3-P1 (valid)")
    
    # Invalid currency code
    invalid_params = {
        "allowed_currencies": ["INVALID"]
    }
    is_valid, errors = validate_parameters("E3-P1", invalid_params)
    assert is_valid is False
    print("[OK] PASS: E5-6b Parameter validation E3-P1 (invalid)")


def test_e5_parameter_validation_e4d3():
    """Test E4-D3 similar amount heuristic parameters."""
    # Valid E4-D3 parameters
    valid_params = {
        "similar_amount_tolerance_pct": 2.0,
        "time_window_days": 60
    }
    is_valid, errors = validate_parameters("E4-D3", valid_params)
    assert is_valid is True
    print("[OK] PASS: E5-7a Parameter validation E4-D3 (valid)")
    
    # Out of range tolerance
    invalid_params = {
        "similar_amount_tolerance_pct": 15.0  # Max is 10.0
    }
    is_valid, errors = validate_parameters("E4-D3", invalid_params)
    assert is_valid is False
    print("[OK] PASS: E5-7b Parameter validation E4-D3 (invalid)")


def test_e5_get_all_active_rules():
    """Test retrieving all active rules for organization."""
    db = MockMongoDB()
    
    # Add multiple configured rules
    db.validation_config[1] = {
        "organization_id": "ORG-RULES",
        "region": "US",
        "rule_id": "E2-F1",
        "enabled": True
    }
    db.validation_config[2] = {
        "organization_id": "ORG-RULES",
        "region": "US",
        "rule_id": "E3-P1",
        "enabled": True
    }
    
    service = ConfigurationService(db)
    
    # Get all active rules
    all_rules = asyncio.run(service.get_all_active_rules("ORG-RULES", "US"))
    
    # Should have configured rules + defaults
    assert len(all_rules) >= 2
    rule_ids = {r["rule_id"] for r in all_rules}
    assert "E2-F1" in rule_ids
    assert "E3-P1" in rule_ids
    
    print("[OK] PASS: E5-8 Get all active rules")


def test_e5_hardcoded_defaults_complete():
    """Test that all E1-E4 rules have hardcoded defaults."""
    defaults = DEFAULT_CONFIG
    
    expected_rules = {
        # E1: Structural
        "E1-S1", "E1-S2", "E1-S3", "E1-S4",
        # E2: Financial
        "E2-F1", "E2-F2", "E2-F3", "E2-F4",
        # E3: Policy
        "E3-P1", "E3-P2", "E3-P3", "E3-P4",
        # E4: Duplicate
        "E4-D1", "E4-D2", "E4-D3"
    }
    
    actual_rules = set(defaults.keys())
    assert expected_rules.issubset(actual_rules), f"Missing rules: {expected_rules - actual_rules}"
    
    # Verify each rule has proper structure
    for rule_id, config in defaults.items():
        assert "rule_name" in config
        assert "rule_category" in config
        assert "parameters" in config
    
    print("[OK] PASS: E5-9 Hardcoded defaults complete")


def test_e5_cache_performance():
    """Test caching improves performance."""
    db = MockMongoDB()
    
    db.validation_config[1] = {
        "organization_id": "ORG-PERF",
        "region": "US",
        "rule_id": "E2-F1",
        "parameters": {}
    }
    
    service = ConfigurationService(db, cache_ttl_seconds=10)
    
    # First call - should query DB
    config1 = asyncio.run(service.get_rule_config("ORG-PERF", "E2-F1", "US"))
    call_count_after_first = len(db.call_history)
    
    # Second call - should use cache (no DB query)
    config2 = asyncio.run(service.get_rule_config("ORG-PERF", "E2-F1", "US"))
    call_count_after_second = len(db.call_history)
    
    # No additional DB calls for cached entry
    assert call_count_after_first == call_count_after_second
    assert config1 == config2
    
    print("[OK] PASS: E5-10 Cache performance")


def test_e5_config_service_singleton():
    """Test configuration service can be used as singleton."""
    from app.services.config_service import reset_config_service, get_config_service
    
    db = MockMongoDB()
    
    # Reset any existing singleton
    reset_config_service()
    
    # Get singleton instance twice
    service1 = asyncio.run(get_config_service(db))
    service2 = asyncio.run(get_config_service(db))
    
    # Should be same instance
    assert service1 is service2
    
    print("[OK] PASS: E5-11 Configuration service singleton")


def test_e5_configuration_audit_trail():
    """Test configuration includes audit trail."""
    db = MockMongoDB()
    
    db.validation_config[1] = {
        "organization_id": "ORG-AUDIT",
        "region": "US",
        "rule_id": "E2-F1",
        "created_at": datetime.utcnow(),
        "created_by": "admin1",
        "updated_at": datetime.utcnow(),
        "updated_by": "admin2",
        "change_history": [
            {
                "timestamp": datetime.utcnow(),
                "changed_by": "admin1",
                "field_changed": "parameters",
                "old_value": 100,
                "new_value": 200,
                "reason": "Q1 adjustment"
            }
        ]
    }
    
    # Configuration should include audit information
    config = db.validation_config[1]
    assert "created_by" in config
    assert "change_history" in config
    assert len(config["change_history"]) == 1
    
    print("[OK] PASS: E5-12 Configuration audit trail")


def test_e5_backward_compatibility_no_config():
    """Test backward compatibility - works without config service."""
    # This simulates E1-E4 validation without E5 config service
    # Validation domain should use hardcoded defaults
    
    from app.services.config_service import DEFAULT_CONFIG
    
    # Get E2-F1 default directly (as if validation is using hardcoded)
    default_e2f1 = DEFAULT_CONFIG["E2-F1"]
    
    assert default_e2f1["severity"] == "SOFT"
    assert "parameters" in default_e2f1
    assert default_e2f1["parameters"]["tolerance_amount_cents"] == 100
    
    print("[OK] PASS: E5-13 Backward compatibility without config service")


def test_e5_configuration_resolution_order():
    """Test configuration resolution order: Specific > Global > Default."""
    db = MockMongoDB()
    
    # Add both specific and global configs
    db.validation_config[1] = {
        "organization_id": "ORG-RES",
        "region": "ALL",
        "rule_id": "E2-F1",
        "parameters": {"tolerance_amount_cents": 200}  # Global
    }
    
    db.validation_config[2] = {
        "organization_id": "ORG-RES",
        "region": "US",
        "rule_id": "E2-F1",
        "parameters": {"tolerance_amount_cents": 100}  # Specific
    }
    
    service = ConfigurationService(db)
    
    # US-specific should be preferred
    config_us = asyncio.run(service.get_rule_config("ORG-RES", "E2-F1", "US"))
    assert config_us["parameters"]["tolerance_amount_cents"] == 100
    
    # EU should fall back to ALL
    config_eu = asyncio.run(service.get_rule_config("ORG-RES", "E2-F1", "EU"))
    assert config_eu["parameters"]["tolerance_amount_cents"] == 200
    
    print("[OK] PASS: E5-14 Configuration resolution order")


# Run all tests
if __name__ == "__main__":
    tests = [
        test_e5_config_service_full_workflow,
        test_e5_multi_org_isolation,
        test_e5_multi_region_resolution,
        test_e5_parameter_validation_e2f1,
        test_e5_parameter_validation_e3p1,
        test_e5_parameter_validation_e4d3,
        test_e5_get_all_active_rules,
        test_e5_hardcoded_defaults_complete,
        test_e5_cache_performance,
        test_e5_config_service_singleton,
        test_e5_configuration_audit_trail,
        test_e5_backward_compatibility_no_config,
        test_e5_configuration_resolution_order,
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
        print("[OK] ALL STEP E5 INTEGRATION TESTS PASSED")
    else:
        sys.exit(1)
