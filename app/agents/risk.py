# app/agents/risk.py
"""
Risk & Approval Agent (rule-based stub).

Exported: run_risk_and_approval(db, invoice) -> AgentResponse dict

Behavior (simple POC):
 - Reads env / DB-configurable thresholds (e.g., AUTO_APPROVE_LIMIT)
 - If invoice amount <= auto_approve_limit => returns decision: auto_approve
 - Else: returns status "needs_human" with next_agent "ApprovalAgent" and suggested approver level
 - Supports vendor blacklist: if vendor in blacklist => always needs human
 - Output follows the AgentResponse envelope used by orchestrator
"""

import os
from typing import Dict, Any
from datetime import datetime
import math

AGENT_NAME = "RiskApprovalAgent"

def _now_iso():
    return datetime.utcnow().isoformat() + "Z"

def _get_env_limit():
    # default to 50000 (currency unit)
    try:
        val = os.environ.get("AUTO_APPROVE_LIMIT", "50000")
        return float(val)
    except Exception:
        return 50000.0

def _get_approval_rules(db):
    """
    Optionally read rules from db (if you prefer dynamic tuning).
    Expect a collection 'approval_rules' with a single doc:
      { "_id":"defaults", "auto_approve_limit":50000, "vendor_blacklist": ["V999"] }
    """
    try:
        doc = db.approval_rules.find_one({"_id": "defaults"})
        if doc:
            return {
                "auto_approve_limit": float(doc.get("auto_approve_limit", _get_env_limit())),
                "vendor_blacklist": doc.get("vendor_blacklist", []),
            }
    except Exception:
        pass
    return {"auto_approve_limit": _get_env_limit(), "vendor_blacklist": []}

def run_risk_and_approval(db, invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous function (call via asyncio.to_thread).
    Returns AgentResponse:
      - decision: "auto_approve" or "needs_human"
      - next_agent: "ApprovalAgent" if needs_human, else null
      - confidence: 0..1 (simple heuristic)
      - suggested_approver: "manager" | "director"
    """
    invoice_id = invoice.get("_id") or invoice.get("header", {}).get("invoice_ref")
    header = invoice.get("header", {}) or {}
    amount = header.get("amount") or header.get("grand_total", {}).get("value") or 0.0
    vendor = invoice.get("vendor", {}) or {}
    vendor_id = vendor.get("vendor_id") or vendor.get("_id") or header.get("vendor_number")

    rules = _get_approval_rules(db)
    limit = rules["auto_approve_limit"]
    blacklist = rules["vendor_blacklist"]

    result = {
        "agent": AGENT_NAME,
        "invoice_id": invoice_id,
        "status": "completed",
        "result": {},
        "next_agent": None,
        "score": 1.0,
        "errors": [],
        "timestamp": _now_iso(),
    }

    try:
        # vendor blacklist => manual
        if vendor_id and vendor_id in blacklist:
            result["status"] = "needs_human"
            result["result"] = {
                "reason": "vendor_blacklisted",
                "vendor_id": vendor_id,
                "amount": amount,
            }
            result["next_agent"] = "ApprovalAgent"
            result["score"] = 0.95
            result["result"]["suggested_approver"] = "security_team"
            return result

        # Auto-approve if amount <= limit
        try:
            amt_val = float(amount)
        except Exception:
            amt_val = 0.0

        if amt_val <= float(limit):
            # auto-approve decision
            result["decision"] = "auto_approve"
            result["result"] = {"reason": "below_threshold", "amount": amt_val, "threshold": limit}
            result["status"] = "completed"
            result["next_agent"] = None
            result["score"] = 0.98
            return result

        # High-value -> needs human approval, suggest level
        # Simple heuristic:  limit*3 -> director, else manager
        suggested = "manager"
        if amt_val >= float(limit) * 3.0:
            suggested = "director"
        result["status"] = "needs_human"
        result["next_agent"] = "ApprovalAgent"
        result["result"] = {"reason": "exceeds_threshold", "amount": amt_val, "threshold": limit, "suggested_approver": suggested}
        result["score"] = max(0.0, min(1.0, 1 - (limit / (amt_val + 1))))  # simplistic confidence
        return result

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))
        result["score"] = 0.0
        return result
