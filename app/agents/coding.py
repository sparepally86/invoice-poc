# app/agents/coding.py
"""
Simple rule-based Coding Agent.

Function: run_coding(db, invoice) -> dict (AgentResponse envelope)

Behavior:
 - Look up vendor mapping in db.vendors (if available).
 - Look up buyer-companycode mapping (simple rules or DB collection).
 - For each invoice line, attempt to assign GL account, cost center, profit center.
 - Provide confidence (0..1) per line and an overall score.
 - Return a structured AgentResponse (per Agent IO schema).
"""

from typing import Dict, Any, List
from datetime import datetime
from app.agents._common import ensure_agent_response

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
                    for m in matches:
                        if (m.get("item_index") == idx or m.get("invoice_item_index") == idx) and m.get("po_line_coding"):
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