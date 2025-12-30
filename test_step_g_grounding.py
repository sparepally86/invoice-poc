#!/usr/bin/env python
"""
Test Step G: ExplainAgent Grounding on Validation Issues

This test verifies:
1. ExplainAgent accepts validation_result parameter
2. When validation_result is provided, grounded explanations are generated
3. Each explanation includes rule_code, category, severity
4. No new issues are introduced beyond what's in ValidationResult
5. All issues in ValidationResult get exactly one explanation
"""

import sys
import json
from unittest.mock import Mock, MagicMock, patch

# Add app to path
sys.path.insert(0, ".")

from app.agents.explain import run_explain, _generate_grounded_explanations


def test_run_explain_with_validation_result():
    """Test that run_explain uses validation_result when provided"""
    
    # Mock database
    mock_db = MagicMock()
    mock_db.telemetry = MagicMock()
    mock_db.telemetry.insert_one = Mock()
    
    # Sample invoice
    invoice = {
        "_id": "test-invoice-001",
        "header": {
            "invoice_number": "INV-001",
            "vendor": "Test Vendor",
            "total_amount": 1000.00,
            "po_number": "PO-123"
        },
        "lines": []
    }
    
    # Sample ValidationResult with multiple issues
    validation_result = {
        "status": "WARN",
        "issues": [
            {
                "code": "TOTAL_MISMATCH",
                "category": "FINANCIAL",
                "severity": "SOFT",
                "field": "header.total_amount",
                "message": "Invoice total doesn't match sum of line items",
                "metadata": {"tolerance": "2%"}
            },
            {
                "code": "MISSING_FIELD",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": "header.invoice_date",
                "message": "Invoice date is required but missing",
                "metadata": {}
            }
        ],
        "summary": {
            "hard_failures": 1,
            "soft_warnings": 1
        },
        "validated_at": "2024-01-01T00:00:00Z"
    }
    
    # Triggering step (for fallback)
    triggering_step = {
        "agent": "POMatchingAgent",
        "result": {}
    }
    
    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.call_llm = Mock(return_value="This is a test explanation.")
    mock_llm.model = "gpt-4"
    
    # Mock rate limiter
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.is_allowed = Mock(return_value=True)
    mock_rate_limiter.allow_request = Mock(return_value=True)
    
    with patch("app.agents.explain.get_llm_client", return_value=mock_llm):
        with patch("app.agents.explain.get_rate_limiter", return_value=mock_rate_limiter):
            with patch("app.agents.explain.search_invoice", return_value=[]):
                # Call run_explain WITH validation_result (Step G)
                result = run_explain(mock_db, invoice, triggering_step, validation_result=validation_result)
    
    # Verify response structure
    print("\n✓ run_explain returned successfully")
    assert isinstance(result, dict), "Result should be a dict"
    print("✓ Result is a dict")
    
    assert result["agent"] == "ExplainAgent", "Agent name should be ExplainAgent"
    print("✓ Agent name is correct")
    
    assert result["status"] == "completed", "Status should be completed"
    print("✓ Status is completed")
    
    # Step G: Verify grounded output format
    assert "result" in result, "Result should have 'result' key"
    result_obj = result["result"]
    
    assert "issue_explanations" in result_obj, "Result should have 'issue_explanations' (Step G)"
    print("✓ Result has issue_explanations array")
    
    issue_explanations = result_obj["issue_explanations"]
    assert isinstance(issue_explanations, list), "issue_explanations should be a list"
    assert len(issue_explanations) == 2, f"Should have 2 explanations (one per issue), got {len(issue_explanations)}"
    print(f"✓ Got {len(issue_explanations)} issue explanations (one per issue)")
    
    # Verify each explanation has required fields
    for i, explanation in enumerate(issue_explanations):
        print(f"\n  Issue {i+1} Explanation:")
        assert "rule_code" in explanation, f"Explanation {i} missing rule_code"
        assert "category" in explanation, f"Explanation {i} missing category"
        assert "severity" in explanation, f"Explanation {i} missing severity"
        assert "explanation" in explanation, f"Explanation {i} missing explanation text"
        
        print(f"    - rule_code: {explanation['rule_code']}")
        print(f"    - category: {explanation['category']}")
        print(f"    - severity: {explanation['severity']}")
        print(f"    - explanation: {explanation['explanation'][:50]}...")
    
    # Verify rule codes match ValidationResult
    rule_codes_from_explanation = [ex["rule_code"] for ex in issue_explanations]
    rule_codes_from_validation = [issue["code"] for issue in validation_result["issues"]]
    
    assert sorted(rule_codes_from_explanation) == sorted(rule_codes_from_validation), \
        f"Rule codes don't match. Explanation: {rule_codes_from_explanation}, Validation: {rule_codes_from_validation}"
    print("\n✓ Rule codes match ValidationResult exactly")
    
    # Verify no hallucinated issues
    assert len(issue_explanations) == len(validation_result["issues"]), \
        f"Number of explanations ({len(issue_explanations)}) should match validation issues ({len(validation_result['issues'])})"
    print("✓ No hallucinated issues - explanation count matches validation count")
    
    # Verify categories and severities match
    for explanation in issue_explanations:
        matching_issue = next(
            (issue for issue in validation_result["issues"] if issue["code"] == explanation["rule_code"]),
            None
        )
        assert matching_issue is not None, f"No matching issue for rule_code {explanation['rule_code']}"
        assert explanation["category"] == matching_issue["category"], \
            f"Category mismatch for {explanation['rule_code']}"
        assert explanation["severity"] == matching_issue["severity"], \
            f"Severity mismatch for {explanation['rule_code']}"
    
    print("✓ Categories and severities match ValidationResult exactly")
    
    # Verify AI metadata includes grounding flag
    assert "ai" in result, "Result should have 'ai' metadata"
    ai_metadata = result["ai"]
    assert ai_metadata.get("grounding_enabled") == True, "grounding_enabled should be True in AI metadata"
    print("✓ Grounding enabled flag set in AI metadata")
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED ✓")
    print("="*60)


def test_run_explain_fallback_without_validation_result():
    """Test that run_explain falls back to legacy behavior without validation_result"""
    
    # Mock database
    mock_db = MagicMock()
    mock_db.telemetry = MagicMock()
    mock_db.telemetry.insert_one = Mock()
    
    # Sample invoice
    invoice = {
        "_id": "test-invoice-002",
        "header": {
            "invoice_number": "INV-002",
            "vendor": "Test Vendor 2",
            "total_amount": 500.00,
        },
        "lines": []
    }
    
    # Triggering step (legacy)
    triggering_step = {
        "agent": "ValidationAgent",
        "result": {
            "codes": ["MISSING_VENDOR"],
            "messages": ["Vendor not found"]
        }
    }
    
    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.call_llm = Mock(return_value="Legacy explanation text")
    mock_llm.model = "gpt-4"
    
    # Mock rate limiter
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.allow_request = Mock(return_value=True)
    
    with patch("app.agents.explain.get_llm_client", return_value=mock_llm):
        with patch("app.agents.explain.get_rate_limiter", return_value=mock_rate_limiter):
            with patch("app.agents.explain.search_invoice", return_value=[]):
                # Call run_explain WITHOUT validation_result (legacy fallback)
                result = run_explain(mock_db, invoice, triggering_step, validation_result=None)
    
    # Verify fallback response structure
    print("\n✓ run_explain fallback returned successfully")
    assert result["agent"] == "ExplainAgent"
    print("✓ Agent name is correct")
    
    # Legacy format should have explanation_text, not issue_explanations
    result_obj = result["result"]
    assert "explanation_text" in result_obj, "Fallback should have explanation_text"
    print("✓ Fallback uses legacy format with explanation_text")
    
    # Should NOT have issue_explanations in fallback mode
    assert "issue_explanations" not in result_obj, "Fallback should not have issue_explanations"
    print("✓ Fallback correctly omits issue_explanations")
    
    # Verify AI metadata shows grounding NOT enabled
    ai_metadata = result["ai"]
    grounding_enabled = ai_metadata.get("grounding_enabled", False)
    assert grounding_enabled == False or "grounding_enabled" not in ai_metadata, \
        "Fallback should not have grounding_enabled=True"
    print("✓ Grounding disabled in fallback mode")
    
    print("\n" + "="*60)
    print("FALLBACK TEST PASSED ✓")
    print("="*60)


if __name__ == "__main__":
    try:
        test_run_explain_with_validation_result()
        test_run_explain_fallback_without_validation_result()
        print("\n" + "="*60)
        print("ALL STEP G TESTS COMPLETED SUCCESSFULLY ✓✓✓")
        print("="*60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
