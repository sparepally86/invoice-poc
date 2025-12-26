#!/usr/bin/env python
"""
Integration test to verify telemetry structure in workflow step.
Shows what will be stored in MongoDB.
"""

import os
import sys
import json
from pathlib import Path
from unittest.mock import Mock

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Enable telemetry
os.environ["TELEMETRY_WRITE"] = "true"
os.environ["RAG_ENABLED"] = "false"
os.environ["LLM_PROVIDER"] = "noop"

from app.agents.explain import run_explain

def main():
    print("\n" + "="*70)
    print("TELEMETRY WORKFLOW STEP STRUCTURE TEST")
    print("="*70 + "\n")
    
    # Mock DB
    mock_db = Mock()
    mock_db.telemetry = Mock()
    mock_db.telemetry.insert_one = Mock()
    
    # Sample invoice and validation step
    invoice = {
        "_id": "inv-20241226-001",
        "header": {
            "invoice_number": "INV-001",
            "vendor_name": "ACME Corp",
            "amount": 5000,
            "po_number": "PO-12345"
        }
    }
    
    triggering_step = {
        "agent": "ValidationAgent",
        "status": "completed",
        "result": {
            "codes": ["PO_AMOUNT_MISMATCH"],
            "messages": ["Invoice amount $5000 does not match PO amount $4500"],
            "errors": []
        }
    }
    
    print("Input:")
    print(f"  Invoice ID: {invoice['_id']}")
    print(f"  Vendor: {invoice['header']['vendor_name']}")
    print(f"  Amount: {invoice['header']['amount']}")
    print(f"  Validation: {triggering_step['result']['codes']}\n")
    
    # Run ExplainAgent
    response = run_explain(mock_db, invoice, triggering_step)
    
    print("="*70)
    print("WORKFLOW STEP RESPONSE (what gets stored in _workflow.steps[])")
    print("="*70 + "\n")
    
    print(json.dumps(response, indent=2))
    
    print("\n" + "="*70)
    print("TELEMETRY SECTION (in ai.telemetry)")
    print("="*70 + "\n")
    
    telemetry = response.get("ai", {}).get("telemetry")
    if telemetry:
        print(json.dumps(telemetry, indent=2))
        print("\n✓ Telemetry successfully stored in workflow step")
        print("\nAccess path in MongoDB:")
        print("  db.invoices.findOne({_id: '...'})._workflow.steps[].ai.telemetry")
    else:
        print("✗ NO TELEMETRY FOUND - This should not happen with TELEMETRY_WRITE=true")
        return 1
    
    print("\n" + "="*70)
    print("VERIFICATION CHECKLIST")
    print("="*70)
    
    checks = [
        ("prompt_hash present", "prompt_hash" in telemetry),
        ("prompt_hash is 16 chars", len(telemetry.get("prompt_hash", "")) == 16),
        ("model populated", telemetry.get("model") is not None),
        ("latency_ms present", "latency_ms" in telemetry),
        ("latency_ms is integer", isinstance(telemetry.get("latency_ms"), int)),
        ("token_usage dict present", isinstance(telemetry.get("token_usage"), dict)),
        ("prompt_tokens in token_usage", "prompt_tokens" in telemetry.get("token_usage", {})),
        ("completion_tokens in token_usage", "completion_tokens" in telemetry.get("token_usage", {})),
        ("total_tokens in token_usage", "total_tokens" in telemetry.get("token_usage", {})),
        ("retrieval_count present", "retrieval_count" in telemetry),
        ("invoice_id present", "invoice_id" in telemetry),
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("ALL CHECKS PASSED ✓")
        print("="*70 + "\n")
        return 0
    else:
        print("SOME CHECKS FAILED ✗")
        print("="*70 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
