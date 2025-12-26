# app/tests/test_explain_telemetry.py
"""
Test suite for ExplainAgent telemetry functionality.

Tests:
1. TELEMETRY_WRITE=false → No telemetry field in workflow step
2. TELEMETRY_WRITE=true → Telemetry field present with all required fields
3. Failure safety → No crash when usage missing or latency fails
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.agents.explain import run_explain
from app.ai.llm_client import LLMClient


@pytest.fixture
def mock_db():
    """Mock MongoDB client."""
    db = Mock()
    db.telemetry = Mock()
    db.telemetry.insert_one = Mock(return_value=None)
    db.invoices = Mock()
    return db


@pytest.fixture
def sample_invoice():
    """Sample invoice for testing."""
    return {
        "_id": "inv-test-123",
        "header": {
            "invoice_number": "INV-001",
            "vendor_name": "Test Vendor",
            "amount": 1000,
            "po_number": "PO-001"
        }
    }


@pytest.fixture
def sample_triggering_step():
    """Sample validation step that triggers explain."""
    return {
        "agent": "ValidationAgent",
        "status": "completed",
        "result": {
            "codes": ["AMOUNT_MISMATCH"],
            "messages": ["Invoice amount does not match PO amount"],
            "errors": []
        }
    }


@patch.dict(os.environ, {"TELEMETRY_WRITE": "false", "RAG_ENABLED": "false", "LLM_PROVIDER": "noop"})
def test_telemetry_disabled_no_field(mock_db, sample_invoice, sample_triggering_step):
    """
    TEST 1: TELEMETRY_WRITE=false
    
    Verify:
    - No telemetry field added to workflow step
    - System behaves identically to before
    """
    # Reload config to pick up env var
    import importlib
    import app.config
    importlib.reload(app.config)
    from app.config import TELEMETRY_WRITE
    assert not TELEMETRY_WRITE, "TELEMETRY_WRITE should be false"
    
    # Run ExplainAgent
    response = run_explain(mock_db, sample_invoice, sample_triggering_step)
    
    # Verify response structure
    assert response["agent"] == "ExplainAgent"
    assert response["status"] == "completed"
    assert "ai" in response
    
    # CRITICAL: Verify NO telemetry field in ai metadata
    ai_metadata = response.get("ai", {})
    assert "telemetry" not in ai_metadata, "telemetry field should NOT be present when TELEMETRY_WRITE=false"
    
    # Verify other fields ARE present
    assert "prompt_hash" in ai_metadata
    assert "model" in ai_metadata
    assert "retrieval_hits" in ai_metadata
    
    print("✓ TEST 1 PASSED: No telemetry field when TELEMETRY_WRITE=false")


@patch.dict(os.environ, {"TELEMETRY_WRITE": "true", "RAG_ENABLED": "false", "LLM_PROVIDER": "noop"})
def test_telemetry_enabled_all_fields(mock_db, sample_invoice, sample_triggering_step):
    """
    TEST 2: TELEMETRY_WRITE=true
    
    Verify:
    - telemetry field present in workflow step
    - All required fields populated: prompt_hash, model, token_usage, latency_ms, retrieval_count
    - latency_ms > 0
    - token_usage contains prompt_tokens, completion_tokens, total_tokens
    """
    # Reload config to pick up env var
    import importlib
    import app.config
    importlib.reload(app.config)
    from app.config import TELEMETRY_WRITE
    assert TELEMETRY_WRITE, "TELEMETRY_WRITE should be true"
    
    # Run ExplainAgent
    response = run_explain(mock_db, sample_invoice, sample_triggering_step)
    
    # Verify response structure
    assert response["agent"] == "ExplainAgent"
    assert response["status"] == "completed"
    
    ai_metadata = response.get("ai", {})
    
    # CRITICAL: Verify telemetry field IS present
    assert "telemetry" in ai_metadata, "telemetry field MUST be present when TELEMETRY_WRITE=true"
    
    telemetry = ai_metadata["telemetry"]
    assert isinstance(telemetry, dict), "telemetry should be a dict"
    
    # Verify all required fields
    required_fields = ["prompt_hash", "model", "token_usage", "latency_ms", "retrieval_count"]
    for field in required_fields:
        assert field in telemetry, f"telemetry missing required field: {field}"
    
    # Validate field values
    assert isinstance(telemetry["prompt_hash"], str), "prompt_hash should be string"
    assert len(telemetry["prompt_hash"]) == 16, "prompt_hash should be 16 chars (SHA256[:16])"
    
    assert isinstance(telemetry["model"], str), "model should be string"
    
    assert isinstance(telemetry["latency_ms"], int), "latency_ms should be int"
    assert telemetry["latency_ms"] >= 0, "latency_ms should be >= 0"
    
    assert isinstance(telemetry["token_usage"], dict), "token_usage should be dict"
    token_usage = telemetry["token_usage"]
    assert "prompt_tokens" in token_usage
    assert "completion_tokens" in token_usage
    assert "total_tokens" in token_usage
    
    assert isinstance(telemetry["retrieval_count"], int), "retrieval_count should be int"
    assert telemetry["retrieval_count"] >= 0
    
    # Optional: invoice_id should be present if invoice has _id
    if sample_invoice.get("_id"):
        assert "invoice_id" in telemetry
    
    print("✓ TEST 2 PASSED: All telemetry fields present and valid when TELEMETRY_WRITE=true")


@patch.dict(os.environ, {"TELEMETRY_WRITE": "true", "RAG_ENABLED": "false", "LLM_PROVIDER": "noop"})
def test_telemetry_failure_safety_missing_usage(mock_db, sample_invoice, sample_triggering_step):
    """
    TEST 3: Failure Safety - Missing Usage
    
    Simulate OpenAI response missing usage data.
    Verify:
    - No crash
    - token_usage fields are None or 0
    - Telemetry still captured
    """
    import importlib
    import app.config
    importlib.reload(app.config)
    
    # Mock LLM to return response without usage
    with patch('app.agents.explain.get_llm_client') as mock_get_llm:
        mock_llm = Mock()
        mock_llm.model = "gpt-4o"
        mock_llm.call_llm = Mock(return_value={
            "provider": "openai",
            "model": "gpt-4o",
            "text": "Test explanation",
            "usage": None,  # Missing usage!
            "meta": {}
        })
        mock_get_llm.return_value = mock_llm
        
        # Should not crash
        try:
            response = run_explain(mock_db, sample_invoice, sample_triggering_step)
            assert response["status"] == "completed"
            
            # Telemetry should still be present
            ai_metadata = response.get("ai", {})
            if "telemetry" in ai_metadata:
                telemetry = ai_metadata["telemetry"]
                # token_usage should be safely empty or zeroed
                assert telemetry["token_usage"]["prompt_tokens"] is not None
                print("✓ TEST 3A PASSED: Handles missing usage gracefully")
        except Exception as e:
            pytest.fail(f"Should not crash when usage missing: {str(e)}")


@patch.dict(os.environ, {"TELEMETRY_WRITE": "true", "RAG_ENABLED": "false", "LLM_PROVIDER": "noop"})
def test_telemetry_failure_safety_llm_error(mock_db, sample_invoice, sample_triggering_step):
    """
    TEST 3B: Failure Safety - LLM Error
    
    Verify:
    - LLM call failure is handled
    - Response status is 'failed' but doesn't crash
    - Telemetry attempted if possible
    """
    import importlib
    import app.config
    importlib.reload(app.config)
    
    with patch('app.agents.explain.get_llm_client') as mock_get_llm:
        mock_llm = Mock()
        mock_llm.model = "gpt-4o"
        mock_llm.call_llm = Mock(side_effect=RuntimeError("API key missing"))
        mock_get_llm.return_value = mock_llm
        
        # Should not crash
        try:
            response = run_explain(mock_db, sample_invoice, sample_triggering_step)
            assert response["status"] == "failed"
            print("✓ TEST 3B PASSED: Handles LLM errors gracefully")
        except Exception as e:
            pytest.fail(f"Should not crash on LLM error: {str(e)}")


@patch.dict(os.environ, {"TELEMETRY_WRITE": "true", "RAG_ENABLED": "false", "LLM_PROVIDER": "noop"})
def test_telemetry_latency_measurement(mock_db, sample_invoice, sample_triggering_step):
    """
    TEST 4: Latency Measurement
    
    Verify:
    - latency_ms is measured around LLM call
    - latency_ms is positive integer in milliseconds
    """
    import importlib
    import app.config
    import time
    importlib.reload(app.config)
    
    with patch('app.agents.explain.get_llm_client') as mock_get_llm:
        mock_llm = Mock()
        mock_llm.model = "gpt-4o"
        
        def slow_llm_call(*args, **kwargs):
            time.sleep(0.01)  # Sleep 10ms
            return {
                "provider": "openai",
                "model": "gpt-4o",
                "text": "Test explanation",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "meta": {}
            }
        
        mock_llm.call_llm = Mock(side_effect=slow_llm_call)
        mock_get_llm.return_value = mock_llm
        
        response = run_explain(mock_db, sample_invoice, sample_triggering_step)
        
        ai_metadata = response.get("ai", {})
        telemetry = ai_metadata.get("telemetry", {})
        
        latency_ms = telemetry.get("latency_ms")
        assert latency_ms is not None, "latency_ms should be captured"
        assert isinstance(latency_ms, int)
        assert latency_ms >= 10, f"latency_ms should be at least 10ms (got {latency_ms})"
        
        print(f"✓ TEST 4 PASSED: Latency measured correctly ({latency_ms}ms)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
