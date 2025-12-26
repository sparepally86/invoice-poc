# app/agents/coding.py
"""
Simple rule-based Coding Agent.

Function: run_coding(db, invoice) -> dict (AgentResponse envelope)
Function: run_coding_nonpo(db, invoice) -> dict (AgentResponse envelope) - for non-PO invoices

Behavior:
 - For PO invoices: Look up vendor mapping in db.vendors (if available).
 - For non-PO invoices: Use static JSON rules file for deterministic vendor-name-based coding.
 - Look up buyer-companycode mapping (simple rules or DB collection).
 - For each invoice line, attempt to assign GL account, cost center, profit center.
 - Provide confidence (0..1) per line and an overall score.
 - Return a structured AgentResponse (per Agent IO schema).
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.agents._common import ensure_agent_response
from app.logging_config import get_logger

logger = get_logger(__name__)

AGENT_NAME = "CodingAgent"

# Fallback rule maps (small, embedded defaults if db not present / mapping missing)
# You can later store these in Mongo (e.g., db.coding_rules)
FALLBACK_VENDOR_GL = {
    # vendor_id: gl_account
    "V0001": "500100",  # travel
    "V0002": "600200",  # consulting
    "V0003": "700300",  # office supplies
}

FALLBACK_COMPANY_COSTCENTER = {
    "1000": "CC1000",
    "2000": "CC2000",
}

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _lookup_vendor_rules(db, vendor_id: str) -> Dict[str, Any]:
    """
    Try to load vendor-specific coding from db.vendors (if stored).
    Expect document shape: { _id: vendor_id, coding_defaults: { gl: '...', cost_center: '...', profit_center: '...' } }
    """
    try:
        if vendor_id:
            doc = db.vendors.find_one({"_id": vendor_id}) or db.vendors.find_one({"vendor_id": vendor_id})
            if doc:
                return doc.get("coding_defaults", {}) or {}
    except Exception:
        pass
    # fallback to embedded map
    gl = FALLBACK_VENDOR_GL.get(vendor_id)
    out = {}
    if gl:
        out["gl_account"] = gl
    return ensure_agent_response("CodingAgent", out)

def _lookup_company_rules(db, companycode: str) -> Dict[str, Any]:
    cc = FALLBACK_COMPANY_COSTCENTER.get(companycode)
    if cc:
        return {"cost_center": cc}
    # try db
    try:
        doc = db.company_codes.find_one({"code": companycode}) if hasattr(db, "company_codes") else None
        if doc:
            return doc.get("coding_defaults", {})
    except Exception:
        pass
    return {}

def run_coding(db, invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous function to be called by orchestrator (via asyncio.to_thread).
    Returns AgentResponse dict with keys:
      - agent, invoice_id, status, result, next_agent, score, timestamp
    """
    invoice_id = invoice.get("_id") or invoice.get("header", {}).get("invoice_ref")
    header = invoice.get("header", {}) or {}
    vendor = invoice.get("vendor", {}) or {}
    vendor_id = vendor.get("vendor_id") or vendor.get("_id") or header.get("vendor_number")
    companycode_from_header = header.get("buyer_companycode") or header.get("buyer_company_code") or None

    # lines/ items
    lines = invoice.get("lines") or invoice.get("items") or []

    agent_response = {
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
        vendor_rules = _lookup_vendor_rules(db, vendor_id)
        company_rules = _lookup_company_rules(db, companycode_from_header)

        results: List[Dict[str, Any]] = []
        overall_score = 0.0
        if not lines:
            # no lines, try to code top-level invoice
            gl = vendor_rules.get("gl_account") or vendor_rules.get("gl") or None
            cc = company_rules.get("cost_center") or None
            if gl or cc:
                overall_score = 0.9
                agent_response["result"]["invoice_level_coding"] = {"gl_account": gl, "cost_center": cc, "confidence": overall_score}
            else:
                overall_score = 0.2
                agent_response["status"] = "partial"
        else:
            for idx, line in enumerate(lines):
                # try vendor rule mapping
                gl = vendor_rules.get("gl_account") or vendor_rules.get("gl")
                cost_center = company_rules.get("cost_center")
                profit_center = vendor_rules.get("profit_center") or company_rules.get("profit_center")

                # If PO line has coding info, prefer that
                # (some PO implementations could store coding on PO lines)
                po_line_coding = None
                if invoice.get("_po_match_result"):
                    # optional field previously set by PO matching
                    pm = invoice["_po_match_result"]
                    # find matched po line mapping (best-effort)
                    matches = pm.get("line_matches") or []
                    # Canonicalize old keys to item_index for backward compatibility
                    for mm in matches:
                        if mm is None or not isinstance(mm, dict):
                            continue
                        if "item_index" not in mm:
                            if "invoice_item_index" in mm:
                                mm["item_index"] = mm.get("invoice_item_index")
                            elif "invoice_item_idx" in mm:
                                mm["item_index"] = mm.get("invoice_item_idx")
                    for m in matches:
                        if m.get("item_index") == idx and m.get("po_line_coding"):
                            po_line_coding = m.get("po_line_coding")
                            break

                final_gl = None
                final_cc = None
                final_pp = None
                confidence = 0.0

                if po_line_coding:
                    final_gl = po_line_coding.get("gl_account")
                    final_cc = po_line_coding.get("cost_center")
                    final_pp = po_line_coding.get("profit_center")
                    confidence = 0.95
                else:
                    if gl:
                        final_gl = gl
                        confidence += 0.6
                    if cost_center:
                        final_cc = cost_center
                        confidence += 0.4
                    if profit_center:
                        final_pp = profit_center
                        confidence += 0.2

                if not (final_gl or final_cc):
                    # try to infer from line text heuristics (very simple)
                    text = (line.get("item_text") or line.get("description") or "").lower()
                    if "travel" in text or "flight" in text or "hotel" in text:
                        final_gl = final_gl or "500100"
                        confidence += 0.2
                    if "consult" in text or "service" in text:
                        final_gl = final_gl or "600200"
                        confidence += 0.1

                # clamp confidence 0..1
                if confidence > 1.0:
                    confidence = 1.0

                results.append(
                    {
                        "item_index": idx,
                        "gl_account": final_gl,
                        "cost_center": final_cc,
                        "profit_center": final_pp,
                        "confidence": round(confidence, 2),
                    }
                )
                overall_score += confidence

            if results:
                overall_score = overall_score / max(1, len(results))
                agent_response["result"]["lines"] = results

        agent_response["score"] = round(overall_score, 2)
        # If average confidence very low, mark partial/needs_human
        if agent_response["score"] < 0.4:
            agent_response["status"] = "partial"
            agent_response["next_agent"] = "HumanCodingReview"
        else:
            agent_response["status"] = "completed"
            agent_response["next_agent"] = None

    except Exception as e:
        agent_response["status"] = "failed"
        agent_response["errors"].append(str(e))
        agent_response["score"] = 0.0

    return ensure_agent_response("CodingAgent", agent_response)


# Path to static coding rules JSON file
_CODING_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "coding_rules.json")

# Cache for loaded rules (loaded once per process)
_cached_rules: Optional[Dict[str, Any]] = None


def _load_static_rules() -> Dict[str, Any]:
    """
    Load coding rules from static JSON file.
    Returns empty dict if file not found or invalid.
    Rules are cached after first load.
    """
    global _cached_rules
    if _cached_rules is not None:
        return _cached_rules

    try:
        rules_path = os.path.abspath(_CODING_RULES_PATH)
        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                _cached_rules = json.load(f)
                logger.info("Loaded coding rules from %s", rules_path)
                return _cached_rules
        else:
            logger.warning("Coding rules file not found: %s", rules_path)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in coding rules file: %s", e)
    except Exception as e:
        logger.error("Failed to load coding rules: %s", e)

    _cached_rules = {}
    return _cached_rules


def _match_vendor_rule(vendor_name: Optional[str], rules: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Match vendor name against rules (case-insensitive, trimmed).
    Returns the rule dict if matched, None otherwise.
    """
    if not vendor_name:
        return None

    vendor_rules = rules.get("vendor_rules", {})
    if not vendor_rules:
        return None

    # Normalize vendor name: trim whitespace, uppercase for comparison
    normalized_name = vendor_name.strip().upper()

    for rule_vendor, rule_data in vendor_rules.items():
        if rule_vendor.strip().upper() == normalized_name:
            return rule_data

    return None


def run_coding_nonpo(db, invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic coding for non-PO invoices using static JSON rules.
    Matches vendor name (case-insensitive) against rules file.

    Returns AgentResponse dict with:
      - agent, invoice_id, status, result, next_agent, score, timestamp
      - result contains: gl_account, rule_applied, matched

    Updates invoice.coding field with:
      - gl_account
      - source = "static_rules"
    """
    invoice_id = invoice.get("_id") or invoice.get("header", {}).get("invoice_ref")
    header = invoice.get("header", {}) or {}
    vendor = invoice.get("vendor", {}) or {}

    # Get vendor name from various possible locations
    vendor_name = (
        vendor.get("name") or
        vendor.get("name_raw") or
        header.get("vendor_name") or
        header.get("vendor") or
        ""
    )

    logger.info("[invoice_id=%s] Running CodingAgent (non-PO) for vendor: %s", invoice_id, vendor_name)

    agent_response = {
        "agent": AGENT_NAME,
        "invoice_id": invoice_id,
        "status": "completed",
        "result": {
            "gl_account": None,
            "rule_applied": None,
            "matched": False,
        },
        "next_agent": None,
        "score": 1.0,
        "errors": [],
        "timestamp": _now_iso(),
    }

    try:
        # Load static rules
        rules = _load_static_rules()

        # Try to match vendor name
        matched_rule = _match_vendor_rule(vendor_name, rules)

        if matched_rule:
            gl_account = matched_rule.get("gl_account")
            agent_response["result"]["gl_account"] = gl_account
            agent_response["result"]["rule_applied"] = vendor_name.strip()
            agent_response["result"]["matched"] = True
            agent_response["score"] = 1.0
            logger.info(
                "[invoice_id=%s] Matched vendor '%s' -> GL account: %s",
                invoice_id, vendor_name, gl_account
            )

            # Update invoice.coding field in DB (invoice-level)
            coding_update = {
                "coding.gl_account": gl_account,
                "coding.source": "static_rules",
            }

            # Also update each line item with coding information (both lines and items arrays)
            lines = invoice.get("lines", []) or []
            items = invoice.get("items", []) or []
            
            updated_lines = []
            for line in lines:
                line_copy = dict(line)
                line_copy["coding"] = {
                    "gl_account": gl_account,
                    "source": "static_rules",
                }
                updated_lines.append(line_copy)

            updated_items = []
            for item in items:
                item_copy = dict(item)
                item_copy["coding"] = {
                    "gl_account": gl_account,
                    "source": "static_rules",
                }
                updated_items.append(item_copy)

            # Add lines and items to the update if we have any
            if updated_lines:
                coding_update["lines"] = updated_lines
            if updated_items:
                coding_update["items"] = updated_items
            agent_response["result"]["lines_coded"] = len(updated_lines)
            agent_response["result"]["items_coded"] = len(updated_items)

            try:
                db.invoices.update_one({"_id": invoice_id}, {"$set": coding_update})
                logger.info("[invoice_id=%s] Updated invoice.coding and %d line items with GL account", invoice_id, len(updated_lines))
            except Exception as e:
                logger.warning("[invoice_id=%s] Failed to update invoice.coding: %s", invoice_id, e)

        else:
            # No rule matched - this is NOT a failure, just no coding applied
            agent_response["result"]["matched"] = False
            agent_response["result"]["note"] = f"No coding rule matched for vendor: {vendor_name}"
            agent_response["score"] = 0.5  # Partial score since no rule matched
            logger.info(
                "[invoice_id=%s] No coding rule matched for vendor '%s'",
                invoice_id, vendor_name
            )

            # Still update invoice.coding to indicate we tried
            coding_update = {
                "coding.gl_account": None,
                "coding.source": "static_rules",
                "coding.note": f"No rule matched for vendor: {vendor_name}",
            }
            try:
                db.invoices.update_one({"_id": invoice_id}, {"$set": coding_update})
            except Exception as e:
                logger.warning("[invoice_id=%s] Failed to update invoice.coding: %s", invoice_id, e)

    except Exception as e:
        agent_response["status"] = "failed"
        agent_response["errors"].append(str(e))
        agent_response["score"] = 0.0
        logger.error("[invoice_id=%s] CodingAgent (non-PO) failed: %s", invoice_id, e)

    return ensure_agent_response("CodingAgent", agent_response)
