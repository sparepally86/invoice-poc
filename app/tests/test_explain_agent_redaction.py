# app/tests/test_explain_agent_redaction.py
"""
Integration tests for ExplainAgent to verify PII redaction works correctly.
"""

import hashlib
from unittest.mock import MagicMock, patch
from app.agents.explain import run_explain, _extract_invoice_context, _extract_validation_results


def test_explain_agent_redacts_pii_before_llm_call():
    """
    Test that ExplainAgent redacts PII from the prompt BEFORE calling the LLM.
    """
    # Mock database and LLM
    mock_db = MagicMock()
    mock_db.telemetry = MagicMock()
    
    # Create invoice with sensitive data
    invoice = {
        "_id": "INV-2024-001",
        "header": {
            "invoice_number": "INV-001",
            "vendor_name": "Acme Corporation",
            "vendor_number": "SUPP001",
            "amount": 5000,
            "currency": "USD"
        },
        "items": [
            {"amount": 5000, "description": "Services"}
        ]
    }
    
    # Create triggering step
    triggering_step = {
        "result": {
            "codes": ["GST_MISMATCH"],
            "messages": ["GST number 18AABCU9603R1Z5 does not match vendor records"]
        }
    }
    
    # Mock LLM client to capture the prompt it receives
    captured_prompts = []
    
    def mock_call_llm(prompt, **kwargs):
        captured_prompts.append(prompt)
        return {
            "provider": "openai",
            "model": "gpt-4o",
            "text": "This invoice has a GST mismatch.",
            "raw": "This invoice has a GST mismatch.",
            "parsed": {"raw": "This invoice has a GST mismatch."},
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": 20
            }
        }
    
    with patch("app.agents.explain.get_llm_client") as mock_llm_client, \
         patch("app.agents.explain.get_rate_limiter") as mock_rate_limiter, \
         patch("app.agents.explain.search_invoice") as mock_search:
        
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.call_llm = mock_call_llm
        mock_llm.model = "gpt-4o"
        mock_llm_client.return_value = mock_llm
        
        mock_rl = MagicMock()
        mock_rl.allow_request.return_value = True
        mock_rate_limiter.return_value = mock_rl
        
        mock_search.return_value = []
        
        # Patch RAG_ENABLED to False for simpler test
        with patch("app.agents.explain.RAG_ENABLED", False):
            # Call ExplainAgent
            response = run_explain(mock_db, invoice, triggering_step)
        
        # Verify response was successful
        assert response["status"] == "completed", f"Unexpected status: {response['status']}"
        
        # Verify LLM was called
        assert len(captured_prompts) == 1, "LLM should be called exactly once"
        
        # Get the prompt that was sent to LLM
        llm_prompt = captured_prompts[0]
        
        # Verify PII is NOT in the LLM prompt
        assert "18AABCU9603R1Z5" not in llm_prompt, "GST number should be redacted before LLM call"
        assert "[REDACTED_GST]" in llm_prompt, "GST should be replaced with redaction marker"
        
        # Verify vendor name is NOT in the LLM prompt
        assert "Acme Corporation" not in llm_prompt, "Vendor name should be redacted before LLM call"
        assert "[REDACTED_VENDOR]" in llm_prompt, "Vendor should be replaced with redaction marker"
        
        # Verify vendor number is NOT in the LLM prompt
        assert "SUPP001" not in llm_prompt, "Vendor number should be redacted before LLM call"
        
        # Verify prompt structure is preserved
        assert "Invoice Context:" in llm_prompt, "Prompt structure should be preserved"
        assert "Validation Results:" in llm_prompt, "Prompt structure should be preserved"
        assert "Task:" in llm_prompt, "Prompt structure should be preserved"
        
        # Verify response includes prompt_hash
        assert "ai" in response, "Response should include 'ai' metadata"
        assert "prompt_hash" in response["ai"], "Response should include prompt_hash"
        
        # Verify prompt_hash is computed on REDACTED prompt
        expected_hash = hashlib.sha256(llm_prompt.encode("utf-8")).hexdigest()[:16]
        assert response["ai"]["prompt_hash"] == expected_hash, "prompt_hash should match redacted prompt"
        
        print("PASS: Test passed: ExplainAgent correctly redacts PII before LLM call")


def test_explain_agent_no_pii_in_telemetry():
    """
    Test that telemetry does not contain raw PII.
    """
    # Mock database with insert_one to capture telemetry
    mock_db = MagicMock()
    inserted_telemetry = []
    
    def capture_insert(doc):
        inserted_telemetry.append(doc)
    
    mock_db.telemetry.insert_one.side_effect = capture_insert
    
    invoice = {
        "_id": "INV-2024-002",
        "header": {
            "vendor_name": "SecretVendor Inc",
            "vendor_number": "V999",
            "amount": 10000,
            "currency": "USD"
        },
        "items": [
            {"amount": 10000, "description": "Confidential Services"}
        ]
    }
    
    triggering_step = {
        "result": {
            "codes": ["EMAIL_VALIDATION_FAILED"],
            "messages": ["Email validation@secretvendor.com failed"]
        }
    }
    
    with patch("app.agents.explain.get_llm_client") as mock_llm_client, \
         patch("app.agents.explain.get_rate_limiter") as mock_rate_limiter, \
         patch("app.agents.explain.search_invoice") as mock_search:
        
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {
            "provider": "openai",
            "model": "gpt-4o",
            "text": "Email validation failed.",
            "raw": "Email validation failed.",
            "parsed": {"raw": "Email validation failed."},
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20
            }
        }
        mock_llm.model = "gpt-4o"
        mock_llm_client.return_value = mock_llm
        
        mock_rl = MagicMock()
        mock_rl.allow_request.return_value = True
        mock_rate_limiter.return_value = mock_rl
        
        mock_search.return_value = []
        
        with patch("app.agents.explain.RAG_ENABLED", False):
            response = run_explain(mock_db, invoice, triggering_step)
        
        # Verify telemetry was logged
        assert len(inserted_telemetry) > 0, "Telemetry should be inserted"
        
        # Check each telemetry entry for raw PII
        for telemetry_entry in inserted_telemetry:
            telemetry_str = str(telemetry_entry)
            assert "SecretVendor Inc" not in telemetry_str, "Raw vendor name should not appear in telemetry"
            assert "V999" not in telemetry_str or "V999" in str(response.get("ai", {}).get("retrieval_hits", [])), \
                "Vendor number should not appear in telemetry unless in retrieval hits"
            assert "validation@secretvendor.com" not in telemetry_str, "Email should not appear in telemetry"
        
        print("PASS: Test passed: Telemetry does not contain raw PII")


def test_prompt_hash_reflects_redacted_content():
    """
    Test that prompt_hash is computed on the redacted prompt, not the original.
    """
    mock_db = MagicMock()
    mock_db.telemetry = MagicMock()
    
    invoice = {
        "_id": "INV-2024-003",
        "header": {
            "vendor_name": "TestVendor",
            "vendor_number": "TV001",
            "amount": 1000,
            "currency": "USD"
        },
        "items": [
            {"amount": 1000}
        ]
    }
    
    triggering_step = {
        "result": {
            "codes": ["TEST"],
            "messages": ["Test message with PAN AAAPA1234A"]
        }
    }
    
    captured_hashes = {}
    
    def mock_call_llm(prompt, **kwargs):
        # Calculate what the hash would be on the redacted prompt
        captured_hashes["llm_received"] = prompt
        return {
            "provider": "openai",
            "model": "gpt-4o",
            "text": "Test response",
            "raw": "Test response",
            "parsed": {"raw": "Test response"},
            "usage": {"prompt_tokens": 100, "completion_tokens": 10}
        }
    
    with patch("app.agents.explain.get_llm_client") as mock_llm_client, \
         patch("app.agents.explain.get_rate_limiter") as mock_rate_limiter, \
         patch("app.agents.explain.search_invoice") as mock_search:
        
        mock_llm = MagicMock()
        mock_llm.call_llm = mock_call_llm
        mock_llm.model = "gpt-4o"
        mock_llm_client.return_value = mock_llm
        
        mock_rl = MagicMock()
        mock_rl.allow_request.return_value = True
        mock_rate_limiter.return_value = mock_rl
        
        mock_search.return_value = []
        
        with patch("app.agents.explain.RAG_ENABLED", False):
            response = run_explain(mock_db, invoice, triggering_step)
        
        # Get the prompt the LLM received
        redacted_prompt = captured_hashes["llm_received"]
        
        # Calculate what the hash should be
        expected_hash = hashlib.sha256(redacted_prompt.encode("utf-8")).hexdigest()[:16]
        
        # Get the hash from response
        actual_hash = response["ai"]["prompt_hash"]
        
        assert actual_hash == expected_hash, \
            f"Prompt hash mismatch: expected {expected_hash}, got {actual_hash}"
        
        # Verify that the prompt contains redaction markers
        assert "[REDACTED" in redacted_prompt, "Redacted prompt should contain redaction markers"
        
        print("PASS: Test passed: Prompt hash correctly reflects redacted content")


if __name__ == "__main__":
    test_explain_agent_redacts_pii_before_llm_call()
    test_explain_agent_no_pii_in_telemetry()
    test_prompt_hash_reflects_redacted_content()
    print("\nPASS: All integration tests passed!")
