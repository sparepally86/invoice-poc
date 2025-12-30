"""
Unit tests for ConfigurationService.

Tests:
- Configuration loading and caching
- Fallback to hardcoded defaults
- Cache invalidation
- Parameter validation
- Multi-tenant isolation
- Multi-region resolution
"""

import asyncio
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, AsyncMock
import pymongo

# Mock database for testing
class MockFindResult:
    def __init__(self, data):
        self.data = data
    
    def sort(self, sort_spec):
        return self
    
    def __iter__(self):
        return iter(self.data)


class MockCollection:
    def __init__(self, data=None):
        self.data = data or {}
    
    def find_one(self, query):
        for doc in self.data.values():
            match = True
            for key, value in query.items():
                if "$ne" in value:
                    if doc.get(key) == value["$ne"]:
                        match = False
                elif "$gte" in value or "$lte" in value:
                    doc_val = doc.get(key)
                    if "$gte" in value and doc_val < value["$gte"]:
                        match = False
                    if "$lte" in value and doc_val > value["$lte"]:
                        match = False
                elif key.startswith("_"):
                    continue
                else:
                    if doc.get(key) != value:
                        match = False
            if match:
                return doc
        return None
    
    def find(self, query):
        results = []
        for doc in self.data.values():
            match = True
            for key, value in query.items():
                if isinstance(value, dict):
                    if "$in" in value:
                        if doc.get(key) not in value["$in"]:
                            match = False
                else:
                    if doc.get(key) != value:
                        match = False
            if match:
                results.append(doc)
        return MockFindResult(results)
    
    def insert_one(self, doc):
        doc_id = doc.get("_id", len(self.data))
        self.data[doc_id] = doc
        return Mock(inserted_id=doc_id)
    
    def update_one(self, query, update, upsert=False):
        pass

class MockFindResult:
    def __init__(self, data):
        self.data = data
    
    def sort(self, sort_spec):
        return self
    
    def __iter__(self):
        return iter(self.data)

class MockDB:
    def __init__(self):
        self.collections = {}
    
    def get_collection(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]
    
    def __getitem__(self, name):
        return self.get_collection(name)


# Test Imports
try:
    from app.services.config_service import ConfigurationService
    from app.services.config_validator import validate_parameters
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)


def test_config_service_init():
    """Test ConfigurationService initialization."""
    db = MockDB()
    service = ConfigurationService(db, cache_ttl_seconds=300)
    assert service.db is not None
    assert service.cache_ttl_seconds == 300
    assert len(service._cache) == 0
    print("[OK] PASS: ConfigurationService initialization")


def test_get_rule_config_hardcoded_default():
    """Test getting hardcoded default config when DB has nothing."""
    db = MockDB()
    service = ConfigurationService(db)
    
    # Get default config for E2-F1 (not in DB)
    config = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    
    assert config["rule_id"] == "E2-F1"
    assert config["rule_name"] == "Amount Tolerance"
    assert config["rule_category"] == "FINANCIAL"
    assert "parameters" in config
    assert config["_source"] == "hardcoded_default"
    print("[OK] PASS: Hardcoded default config retrieval")


def test_get_rule_config_caching():
    """Test that config is cached correctly."""
    db = MockDB()
    service = ConfigurationService(db, cache_ttl_seconds=5)
    
    # First call
    config1 = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    
    # Check cache was populated
    assert f"ORG-001:US:E2-F1" in service._cache
    cached_time, cached_value = service._cache[f"ORG-001:US:E2-F1"]
    
    # Second call should use cache
    config2 = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    
    # Should be same object
    assert config1 == config2
    print("[OK] PASS: Configuration caching works")


def test_cache_expiration():
    """Test that cache expires after TTL."""
    db = MockDB()
    service = ConfigurationService(db, cache_ttl_seconds=0)  # Immediate expiration
    
    # Add to cache with old timestamp
    cache_key = "ORG-001:US:E2-F1"
    old_time = datetime.utcnow() - timedelta(seconds=10)
    service._cache[cache_key] = (old_time, {"test": "data"})
    
    # Get config - should not use cache due to expiration
    config = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    
    # Should get fresh config from default
    assert config["_source"] == "hardcoded_default"
    print("[OK] PASS: Cache expiration works")


def test_multi_tenant_isolation():
    """Test that configurations are isolated by organization."""
    db = MockDB()
    
    # Add configs for different orgs
    config_col = db.get_collection("validation_config")
    config_col.data["1"] = {
        "_id": "1",
        "organization_id": "ORG-001",
        "region": "ALL",
        "rule_id": "E2-F1",
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "enabled": True,
        "parameters": {"tolerance_amount_cents": 500}
    }
    config_col.data["2"] = {
        "_id": "2",
        "organization_id": "ORG-002",
        "region": "ALL",
        "rule_id": "E2-F1",
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "enabled": True,
        "parameters": {"tolerance_amount_cents": 100}
    }
    
    service = ConfigurationService(db)
    
    # Get config for ORG-001
    config1 = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    assert config1["parameters"]["tolerance_amount_cents"] == 500
    
    # Get config for ORG-002
    config2 = asyncio.run(service.get_rule_config("ORG-002", "E2-F1", "US"))
    assert config2["parameters"]["tolerance_amount_cents"] == 100
    
    print("[OK] PASS: Multi-tenant isolation")


def test_region_fallback():
    """Test region fallback logic (specific → ALL → default)."""
    db = MockDB()
    config_col = db.get_collection("validation_config")
    
    # Add only ALL region config
    config_col.data["1"] = {
        "_id": "1",
        "organization_id": "ORG-001",
        "region": "ALL",
        "rule_id": "E2-F1",
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "enabled": True,
        "parameters": {"tolerance_amount_cents": 200}
    }
    
    service = ConfigurationService(db)
    
    # Request specific region (not in DB) - should fall back to ALL
    config = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "EU"))
    assert config["parameters"]["tolerance_amount_cents"] == 200
    
    print("[OK] PASS: Region fallback logic")


def test_cache_invalidation():
    """Test cache invalidation."""
    db = MockDB()
    service = ConfigurationService(db)
    
    # Add something to cache
    service._cache["ORG-001:US:E2-F1"] = (datetime.utcnow(), {"test": "data"})
    service._cache["ORG-001:EU:E2-F1"] = (datetime.utcnow(), {"test": "data"})
    service._cache["ORG-002:US:E2-F1"] = (datetime.utcnow(), {"test": "data"})
    
    # Invalidate only ORG-001
    asyncio.run(service.reload_config("ORG-001"))
    
    # Only ORG-001 entries should be gone
    assert "ORG-001:US:E2-F1" not in service._cache
    assert "ORG-001:EU:E2-F1" not in service._cache
    assert "ORG-002:US:E2-F1" in service._cache
    
    print("[OK] PASS: Cache invalidation")


def test_get_all_active_rules():
    """Test getting all active rules for organization."""
    db = MockDB()
    config_col = db.get_collection("validation_config")
    
    # Add multiple rules
    config_col.data["1"] = {
        "_id": "1",
        "organization_id": "ORG-001",
        "region": "US",
        "rule_id": "E2-F1",
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "enabled": True,
        "parameters": {}
    }
    config_col.data["2"] = {
        "_id": "2",
        "organization_id": "ORG-001",
        "region": "US",
        "rule_id": "E3-P1",
        "rule_name": "Currency Validation",
        "rule_category": "POLICY",
        "enabled": True,
        "parameters": {}
    }
    
    service = ConfigurationService(db)
    
    # Get all rules
    rules = asyncio.run(service.get_all_active_rules("ORG-001", "US"))
    
    # Should have at least the configured rules + defaults
    assert len(rules) >= 2
    rule_ids = {r["rule_id"] for r in rules}
    assert "E2-F1" in rule_ids
    assert "E3-P1" in rule_ids
    
    print("[OK] PASS: Get all active rules")


def test_validate_config_params_valid():
    """Test parameter validation - valid case."""
    db = MockDB()
    service = ConfigurationService(db)
    
    params = {
        "tolerance_amount_cents": 100,
        "tolerance_percentage": 0.5,
        "warning_threshold_percentage": 2.0
    }
    
    is_valid, error_msg = asyncio.run(service.validate_config_params("E2-F1", params))
    
    assert is_valid is True
    assert error_msg is None
    
    print("[OK] PASS: Parameter validation - valid case")


def test_validate_config_params_invalid_type():
    """Test parameter validation - invalid type."""
    db = MockDB()
    service = ConfigurationService(db)
    
    params = {
        "tolerance_amount_cents": "not_a_number"  # Should be int
    }
    
    is_valid, error_msg = asyncio.run(service.validate_config_params("E2-F1", params))
    
    assert is_valid is False
    assert error_msg is not None
    
    print("[OK] PASS: Parameter validation - invalid type")


def test_validate_config_params_out_of_range():
    """Test parameter validation - out of range."""
    db = MockDB()
    service = ConfigurationService(db)
    
    params = {
        "tolerance_percentage": 100.0  # Max is 5.0
    }
    
    is_valid, error_msg = asyncio.run(service.validate_config_params("E2-F1", params))
    
    assert is_valid is False
    assert error_msg is not None
    
    print("[OK] PASS: Parameter validation - out of range")


def test_get_hardcoded_default_all_rules():
    """Test getting all hardcoded defaults."""
    db = MockDB()
    service = ConfigurationService(db)
    
    defaults = service.get_all_default_configs()
    
    # Should have E1-E4 rules
    rule_ids = set(defaults.keys())
    assert "E2-F1" in rule_ids
    assert "E3-P1" in rule_ids
    assert "E4-D1" in rule_ids
    
    # Each should have proper structure
    for rule_id, config in defaults.items():
        assert "rule_id" in config
        assert "rule_name" in config
        assert "rule_category" in config
        assert "enabled" in config
        assert "parameters" in config
    
    print("[OK] PASS: Get all hardcoded defaults")


def test_unknown_rule_id():
    """Test handling of unknown rule ID."""
    db = MockDB()
    service = ConfigurationService(db)
    
    config = asyncio.run(service.get_rule_config("ORG-001", "UNKNOWN-RULE", "US"))
    
    assert config["rule_id"] == "UNKNOWN-RULE"
    assert config["rule_name"] == "Unknown Rule"
    assert config["_source"] == "hardcoded_default"
    
    print("[OK] PASS: Unknown rule ID handling")


def test_concurrent_cache_access():
    """Test concurrent access to cache."""
    db = MockDB()
    service = ConfigurationService(db)
    
    async def fetch_config():
        return await service.get_rule_config("ORG-001", "E2-F1", "US")
    
    # Simulate concurrent access
    configs = asyncio.run(asyncio.gather(
        fetch_config(),
        fetch_config(),
        fetch_config()
    ))
    
    # All should succeed
    assert len(configs) == 3
    assert all(c["rule_id"] == "E2-F1" for c in configs)
    
    # Cache should have single entry
    assert len(service._cache) == 1
    
    print("[OK] PASS: Concurrent cache access")


def test_database_error_fallback():
    """Test fallback to default on database error."""
    db = MockDB()
    
    # Mock a failing collection
    db.collections["validation_config"] = Mock()
    db.collections["validation_config"].find_one = Mock(side_effect=Exception("DB error"))
    
    service = ConfigurationService(db)
    
    # Should fall back to hardcoded default
    config = asyncio.run(service.get_rule_config("ORG-001", "E2-F1", "US"))
    
    assert config["_source"] == "hardcoded_default"
    assert config["rule_id"] == "E2-F1"
    
    print("[OK] PASS: Database error fallback")


# Run all tests
if __name__ == "__main__":
    tests = [
        test_config_service_init,
        test_get_rule_config_hardcoded_default,
        test_get_rule_config_caching,
        test_cache_expiration,
        test_multi_tenant_isolation,
        test_region_fallback,
        test_cache_invalidation,
        test_get_all_active_rules,
        test_validate_config_params_valid,
        test_validate_config_params_invalid_type,
        test_validate_config_params_out_of_range,
        test_get_hardcoded_default_all_rules,
        test_unknown_rule_id,
        test_concurrent_cache_access,
        test_database_error_fallback,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
    
    print(f"\nRESULTS: {passed} passed, {failed} failed")
    if failed == 0:
        print("[OK] ALL CONFIG SERVICE TESTS PASSED")
    else:
        sys.exit(1)
