"""
Test suite for Feedback → Retrieval loop.

Validates:
1. Feedback can be indexed and retrieved with proper metadata
2. Feedback results are distinguishable from invoices (type="feedback")
3. Rejection notes are included in retrieval results
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.storage.vector_client import get_vector_client, InMemoryVectorClient
from app.agents.retrieval import (
    embed_text, index_document, search_invoice, _normalize_hit, retrieve
)


def test_1_feedback_indexing_and_type_preservation():
    """
    Test 1: Accept feedback → reindex → retrieve → verify type="feedback"
    
    Scenario:
    - Create a mock invoice document
    - Index feedback showing a human ACCEPTED this invoice
    - Search for similar invoices
    - Verify feedback result has type="feedback" and is distinguishable
    """
    print("\n=== TEST 1: Feedback Indexing & Type Preservation ===")
    
    # Setup: Clear vector client and create a mock invoice
    vc = get_vector_client()
    if isinstance(vc, InMemoryVectorClient):
        vc.clear()  # Reset for clean test
    
    # Mock invoice
    invoice_id = "inv_test_accept_001"
    mock_invoice = {
        "_id": invoice_id,
        "header": {
            "invoice_ref": "INV-2024-001",
            "vendor": "TechCorp Inc",
            "amount": 50000.00
        },
        "lines": [
            {"description": "Enterprise Software License"}
        ]
    }
    
    # Index the invoice itself
    invoice_text = (
        f"Invoice INV-2024-001 | vendor TechCorp Inc | amount 50000.00 | "
        f"Enterprise Software License"
    )
    invoice_doc_id = f"invoice::{invoice_id}"
    index_document(invoice_doc_id, invoice_text, metadata={
        "type": "invoice",
        "source_id": invoice_id,
        "text_preview": invoice_text[:150]
    })
    print(f"✓ Indexed invoice: {invoice_doc_id}")
    
    # Now index feedback showing acceptance
    feedback_doc = {
        "_id": "fb_test_001",
        "invoice_id": invoice_id,
        "verdict": "accept",
        "notes": "Invoice validated. Vendor records match our PO.",
        "user": "reviewer_alice",
        "created_at": datetime.now(timezone.utc)
    }
    
    # Build feedback text (using improved format)
    parts = []
    parts.append(f"Invoice INV-2024-001")
    parts.append(f"vendor TechCorp Inc")
    parts.append(f"Reviewer accept invoice")
    parts.append(f"Note: Invoice validated. Vendor records match our PO.")
    feedback_text = " | ".join(parts)[:500]
    
    feedback_doc_id = f"feedback::{feedback_doc['_id']}"
    index_document(feedback_doc_id, feedback_text, metadata={
        "type": "feedback",
        "source_invoice": invoice_id,
        "verdict": "accept",
        "text_preview": feedback_text[:150],
        "user": "reviewer_alice",
        "created_at": str(feedback_doc["created_at"])
    })
    print(f"✓ Indexed feedback: {feedback_doc_id}")
    
    # Now search for similar invoices
    results = search_invoice(mock_invoice, k=10, min_score=0.0)
    print(f"✓ Search returned {len(results)} results")
    
    # Find feedback result
    feedback_results = [r for r in results if r["metadata"].get("type") == "feedback"]
    invoice_results = [r for r in results if r["metadata"].get("type") == "invoice"]
    
    assert len(feedback_results) >= 1, f"Expected at least 1 feedback result, got {len(feedback_results)}"
    assert len(invoice_results) >= 1, f"Expected at least 1 invoice result, got {len(invoice_results)}"
    
    print(f"✓ Found {len(feedback_results)} feedback result(s) and {len(invoice_results)} invoice result(s)")
    
    # Validate feedback result structure
    fb_result = feedback_results[0]
    assert fb_result["metadata"]["type"] == "feedback", "Feedback type should be 'feedback'"
    assert fb_result["metadata"]["source_id"] == invoice_id, \
        f"Feedback source_id should match invoice. Got: {fb_result['metadata']['source_id']}, expected: {invoice_id}"
    assert "accept" in fb_result["metadata"]["text_preview"].lower(), "Verdict should appear in preview"
    
    print(f"✓ Feedback result structure correct:")
    print(f"  - type: {fb_result['metadata']['type']}")
    print(f"  - source_id: {fb_result['metadata']['source_id']}")
    print(f"  - preview: {fb_result['metadata']['text_preview']}")
    
    print("✓ TEST 1 PASSED: Feedback indexed, type preserved, retrievable\n")
    return True


def test_2_rejection_notes_inclusion():
    """
    Test 2: Reject + note → reindex → retrieve → verify note in text_preview
    
    Scenario:
    - Create a mock invoice document
    - Index feedback showing a human REJECTED with specific reason
    - Search for similar invoices
    - Verify rejection note is visible in text_preview
    """
    print("\n=== TEST 2: Rejection Notes Inclusion ===")
    
    # Setup
    vc = get_vector_client()
    if isinstance(vc, InMemoryVectorClient):
        vc.clear()
    
    # Mock invoice
    invoice_id = "inv_test_reject_002"
    mock_invoice = {
        "_id": invoice_id,
        "header": {
            "invoice_ref": "INV-2024-002",
            "vendor": "OfficeSupply Ltd",
            "amount": 15000.00
        },
        "lines": [
            {"description": "Office Furniture"}
        ]
    }
    
    # Index invoice
    invoice_text = (
        f"Invoice INV-2024-002 | vendor OfficeSupply Ltd | amount 15000.00 | "
        f"Office Furniture"
    )
    invoice_doc_id = f"invoice::{invoice_id}"
    index_document(invoice_doc_id, invoice_text, metadata={
        "type": "invoice",
        "source_id": invoice_id,
        "text_preview": invoice_text[:150]
    })
    print(f"✓ Indexed invoice: {invoice_doc_id}")
    
    # Index rejection feedback with detailed note
    feedback_doc = {
        "_id": "fb_test_reject_001",
        "invoice_id": invoice_id,
        "verdict": "reject",
        "notes": "Line item 3 has duplicate charge. Total should be 12000 not 15000. Vendor confirmed duplicate entry. Request corrected invoice.",
        "user": "reviewer_bob",
        "created_at": datetime.now(timezone.utc)
    }
    
    # Build feedback text
    parts = []
    parts.append(f"Invoice INV-2024-002")
    parts.append(f"vendor OfficeSupply Ltd")
    parts.append(f"Reviewer reject invoice")
    notes_short = feedback_doc["notes"][:150]
    if len(feedback_doc["notes"]) > 150:
        notes_short += "..."
    parts.append(f"Note: {notes_short}")
    feedback_text = " | ".join(parts)[:500]
    
    feedback_doc_id = f"feedback::{feedback_doc['_id']}"
    index_document(feedback_doc_id, feedback_text, metadata={
        "type": "feedback",
        "source_invoice": invoice_id,
        "verdict": "reject",
        "text_preview": feedback_text[:150],
        "user": "reviewer_bob",
        "created_at": str(feedback_doc["created_at"])
    })
    print(f"✓ Indexed rejection feedback: {feedback_doc_id}")
    
    # Search for similar invoices
    results = search_invoice(mock_invoice, k=10, min_score=0.0)
    print(f"✓ Search returned {len(results)} results")
    
    # Find feedback result
    feedback_results = [r for r in results if r["metadata"].get("type") == "feedback"]
    assert len(feedback_results) >= 1, f"Expected at least 1 feedback result, got {len(feedback_results)}"
    
    fb_result = feedback_results[0]
    preview = fb_result["metadata"]["text_preview"]
    
    # Verify key rejection indicators are in preview
    assert "reject" in preview.lower(), f"'reject' should be in preview: {preview}"
    assert "duplicate" in preview.lower(), f"'duplicate' (from notes) should be in preview: {preview}"
    
    print(f"✓ Rejection notes visible in preview:")
    print(f"  - preview: {preview}")
    print(f"  - contains 'reject': {('reject' in preview.lower())}")
    print(f"  - contains reason detail: {('duplicate' in preview.lower())}")
    
    print("✓ TEST 2 PASSED: Rejection notes preserved and retrievable\n")
    return True


def test_3_no_feedback_graceful_handling():
    """
    Test 3: No feedback → ensure retrieval works without errors
    
    Scenario:
    - Create a fresh invoice with no feedback
    - Search for similar invoices
    - Verify system returns invoice results only (no errors)
    """
    print("\n=== TEST 3: No Feedback Graceful Handling ===")
    
    # Setup
    vc = get_vector_client()
    if isinstance(vc, InMemoryVectorClient):
        vc.clear()
    
    # Mock invoice with no feedback
    invoice_id = "inv_test_no_feedback_003"
    mock_invoice = {
        "_id": invoice_id,
        "header": {
            "invoice_ref": "INV-2024-003",
            "vendor": "NewVendor XYZ",
            "amount": 8000.00
        },
        "lines": [
            {"description": "Consulting Services"}
        ]
    }
    
    # Index the invoice
    invoice_text = (
        f"Invoice INV-2024-003 | vendor NewVendor XYZ | amount 8000.00 | "
        f"Consulting Services"
    )
    invoice_doc_id = f"invoice::{invoice_id}"
    index_document(invoice_doc_id, invoice_text, metadata={
        "type": "invoice",
        "source_id": invoice_id,
        "text_preview": invoice_text[:150]
    })
    print(f"✓ Indexed invoice: {invoice_doc_id}")
    print(f"  - No feedback for this invoice")
    
    # Search for similar invoices (should not error, should return invoice)
    try:
        results = search_invoice(mock_invoice, k=10, min_score=0.0)
        print(f"✓ Search returned {len(results)} result(s) without error")
        
        if results:
            result = results[0]
            assert result["metadata"]["type"] in ["invoice", "feedback", "doc"], \
                f"Result type should be valid, got: {result['metadata']['type']}"
            print(f"✓ Result has valid type: {result['metadata']['type']}")
        else:
            print(f"⚠ Search returned 0 results (acceptable for empty vector DB)")
        
        print("✓ TEST 3 PASSED: No errors with missing feedback\n")
        return True
    except Exception as e:
        print(f"✗ TEST 3 FAILED: Search errored: {e}\n")
        raise


def run_all_tests():
    """Run all feedback-retrieval loop tests."""
    print("\n" + "="*70)
    print("FEEDBACK → RETRIEVAL LOOP TEST SUITE")
    print("="*70)
    
    results = []
    tests = [
        test_1_feedback_indexing_and_type_preservation,
        test_2_rejection_notes_inclusion,
        test_3_no_feedback_graceful_handling,
    ]
    
    for test_fn in tests:
        try:
            passed = test_fn()
            results.append((test_fn.__name__, passed))
        except Exception as e:
            print(f"✗ {test_fn.__name__} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_fn.__name__, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
