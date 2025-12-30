# app/agents/validation.py
"""
ValidationAgent: Thin wrapper around ValidationDomain abstraction.

Responsibilities:
- Delegate all validation logic to ValidationDomain
- Maintain backward compatibility with orchestrator
- Wrap ValidationDomain result in agent response format

Internal Logic:
- All validation rules organized by category (structural, financial, policy, duplicate)
- All rule execution coordinated by ValidationDomain.validate()
- Agent only responsible for response formatting and orchestrator integration
"""

import datetime
from typing import Dict, Any
from app.agents._common import ensure_agent_response
from app.agents.validation_domain import validate


def run_validation(db, invoice_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    ValidationAgent entry point: Delegate to ValidationDomain and wrap response.
    
    Returns an AgentResponse-like dict with structured ValidationResult.
    Maintains backward compatibility with orchestrator.
    """
    # Delegate all validation logic to ValidationDomain
    validation_result = validate(db, invoice_doc)
    
    # Extract validation status
    hard_failures = validation_result["summary"]["hard_failures"]
    issues = validation_result["issues"]
    
    # Maintain backward compatibility: determine if validation passed
    has_hard_failures = hard_failures > 0
    agent_status = "completed" if not has_hard_failures else "needs_human"

    # For backward compatibility with orchestrator, also include old-style result
    result = {
        "valid": not has_hard_failures,
        "issues": issues,
        "field_confidences": {},   # placeholder for later
        "suggestions": {}
    }

    agent_output = {
        "agent": "ValidationAgent",
        "invoice_id": invoice_doc.get("_id") or invoice_doc.get("invoice_id"),
        "status": agent_status,
        "result": result,
        "validation": validation_result,  # Structured ValidationResult from ValidationDomain
        "next_agent": "POMatchingAgent" if not has_hard_failures else None,
        "score": max(0.0, 1.0 - min(1.0, len(issues) / 10.0)),
        "errors": [],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

    return ensure_agent_response("ValidationAgent", agent_output)