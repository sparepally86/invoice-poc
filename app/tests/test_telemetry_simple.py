#!/usr/bin/env python
"""
Simple test validation script - no pytest required.
Tests the telemetry implementation directly.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add workspace root to path
workspace_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, workspace_root)

print(f"Workspace root: {workspace_root}")
print(f"Python path: {sys.path[0]}")

def test_telemetry_disabled():
    """TEST 1: Verify no telemetry when TELEMETRY_WRITE=false"""
    print("\n" + "="*60)
    print("TEST 1: TELEMETRY_WRITE=false - No telemetry field")
    print("="*60)
    
    # Set env var BEFORE importing config
    os.environ["TELEMETRY_WRITE"] = "false"
    os.environ["RAG_ENABLED"] = "false"
    os.environ["LLM_PROVIDER"] = "noop"
    
    # Clear any cached imports
    for key in list(sys.modules.keys()):
        if "app" in key:
            del sys.modules[key]
    
    from app.agents.explain import run_explain
    from app.config import TELEMETRY_WRITE
    
    print(f"TELEMETRY_WRITE = {TELEMETRY_WRITE}")
    assert not TELEMETRY_WRITE, "Config should have TELEMETRY_WRITE=false"
    
    # Mock DB
    mock_db = Mock()
    mock_db.telemetry = Mock()
    mock_db.telemetry.insert_one = Mock()
    
    # Sample data
    invoice = {"_id": "inv-test-123", "header": {"invoice_number": "INV-001"}}
    triggering_step = {"agent": "ValidationAgent", "status": "completed", "result": {"codes": ["TEST"]}}
    
    # Run ExplainAgent
    response = run_explain(mock_db, invoice, triggering_step)
    
    print(f"Response agent: {response.get('agent')}")
    print(f"Response status: {response.get('status')}")
    
    ai_metadata = response.get("ai", {})
    print(f"AI metadata keys: {list(ai_metadata.keys())}")
    
    # CRITICAL CHECK
    if "telemetry" in ai_metadata:
        print("❌ FAILED: telemetry field SHOULD NOT be present when TELEMETRY_WRITE=false")
        return False
    
    if "prompt_hash" not in ai_metadata:
        print("❌ FAILED: prompt_hash SHOULD be present")
        return False
    
    print("✓ PASSED: No telemetry field when TELEMETRY_WRITE=false")
    print(f"  - prompt_hash: {ai_metadata.get('prompt_hash')}")
    print(f"  - model: {ai_metadata.get('model')}")
    return True


def test_telemetry_enabled():
    """TEST 2: Verify telemetry is written when TELEMETRY_WRITE=true"""
    print("\n" + "="*60)
    print("TEST 2: TELEMETRY_WRITE=true - Telemetry field present")
    print("="*60)
    
    # Set env var BEFORE importing
    os.environ["TELEMETRY_WRITE"] = "true"
    os.environ["RAG_ENABLED"] = "false"
    os.environ["LLM_PROVIDER"] = "noop"
    
    # Clear cached imports
    for key in list(sys.modules.keys()):
        if "app" in key:
            del sys.modules[key]
    
    from app.agents.explain import run_explain
    from app.config import TELEMETRY_WRITE
    
    print(f"TELEMETRY_WRITE = {TELEMETRY_WRITE}")
    assert TELEMETRY_WRITE, "Config should have TELEMETRY_WRITE=true"
    
    # Mock DB
    mock_db = Mock()
    mock_db.telemetry = Mock()
    mock_db.telemetry.insert_one = Mock()
    
    # Sample data
    invoice = {"_id": "inv-test-123", "header": {"invoice_number": "INV-001"}}
    triggering_step = {"agent": "ValidationAgent", "status": "completed", "result": {"codes": ["TEST"]}}
    
    # Run ExplainAgent
    response = run_explain(mock_db, invoice, triggering_step)
    
    print(f"Response agent: {response.get('agent')}")
    print(f"Response status: {response.get('status')}")
    
    ai_metadata = response.get("ai", {})
    print(f"AI metadata keys: {list(ai_metadata.keys())}")
    
    # CRITICAL CHECK
    if "telemetry" not in ai_metadata:
        print("❌ FAILED: telemetry field MUST be present when TELEMETRY_WRITE=true")
        return False
    
    telemetry = ai_metadata["telemetry"]
    print(f"\nTelemetry content:")
    print(f"  - prompt_hash: {telemetry.get('prompt_hash')}")
    print(f"  - model: {telemetry.get('model')}")
    print(f"  - latency_ms: {telemetry.get('latency_ms')}")
    print(f"  - retrieval_count: {telemetry.get('retrieval_count')}")
    print(f"  - token_usage keys: {list(telemetry.get('token_usage', {}).keys())}")
    
    # Verify all required fields
    required_fields = ["prompt_hash", "model", "token_usage", "latency_ms", "retrieval_count"]
    for field in required_fields:
        if field not in telemetry:
            print(f"❌ FAILED: telemetry missing required field: {field}")
            return False
    
    # Validate field types
    if not isinstance(telemetry["prompt_hash"], str) or len(telemetry["prompt_hash"]) != 16:
        print(f"❌ FAILED: prompt_hash should be 16-char string (got {telemetry['prompt_hash']})")
        return False
    
    if not isinstance(telemetry["latency_ms"], int) or telemetry["latency_ms"] < 0:
        print(f"❌ FAILED: latency_ms should be non-negative int (got {telemetry['latency_ms']})")
        return False
    
    if not isinstance(telemetry["token_usage"], dict):
        print(f"❌ FAILED: token_usage should be dict")
        return False
    
    print("\n✓ PASSED: All telemetry fields present and valid")
    return True


def test_telemetry_safety():
    """TEST 3: Verify no crash when data is missing"""
    print("\n" + "="*60)
    print("TEST 3: Failure Safety - Handles missing data gracefully")
    print("="*60)
    
    os.environ["TELEMETRY_WRITE"] = "true"
    os.environ["RAG_ENABLED"] = "false"
    os.environ["LLM_PROVIDER"] = "noop"
    
    # Clear cached imports
    for key in list(sys.modules.keys()):
        if "app" in key:
            del sys.modules[key]
    
    from app.agents.explain import run_explain
    
    mock_db = Mock()
    mock_db.telemetry = Mock()
    mock_db.telemetry.insert_one = Mock(side_effect=Exception("DB error"))  # Simulate DB failure
    
    invoice = {"_id": "inv-test-123"}
    triggering_step = {"agent": "ValidationAgent", "status": "completed", "result": {}}
    
    try:
        response = run_explain(mock_db, invoice, triggering_step)
        print(f"Response status: {response.get('status')}")
        print("✓ PASSED: No crash when DB fails or data missing")
        return True
    except Exception as e:
        print(f"❌ FAILED: Crashed with error: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TELEMETRY IMPLEMENTATION TESTS")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Test 1: Disabled", test_telemetry_disabled()))
    except Exception as e:
        print(f"Test 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 1: Disabled", False))
    
    try:
        results.append(("Test 2: Enabled", test_telemetry_enabled()))
    except Exception as e:
        print(f"Test 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 2: Enabled", False))
    
    try:
        results.append(("Test 3: Safety", test_telemetry_safety()))
    except Exception as e:
        print(f"Test 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 3: Safety", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✓ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(p for _, p in results)
    print("\n" + ("="*60))
    if all_passed:
        print("ALL TESTS PASSED ✓")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED ❌")
        sys.exit(1)
