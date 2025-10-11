# app/agents/po_match.py
import os
import datetime
from typing import Dict, Any, List

PRICE_TOL_PCT = float(os.environ.get("PO_PRICE_TOL_PCT", "5.0"))
QTY_TOL_PCT = float(os.environ.get("PO_QTY_TOL_PCT", "0.0"))

def _pct_diff(a: float, b: float) -> float:
    if a == 0:
        return 100.0 if b != 0 else 0.0
    return abs(a - b) / abs(a) * 100.0

def run_po_matching(db, invoice_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic PO matching:
    - Looks for PO by header.po_number (or header.po if used).
    - Compares totals and line-by-line amounts.
    Returns an AgentResponse-like dict.
    """
    header = invoice_doc.get("header", {})
    items = invoice_doc.get("items", []) or []
    po_number = header.get("po_number") or header.get("po") or header.get("po_reference")
    now = datetime.datetime.utcnow().isoformat() + "Z"

    result: Dict[str, Any] = {
        "po_found": False,
        "po_number": None,
        "match_score": 0.0,
        "line_matches": [],
        "tolerance_exceeded": False,
        "summary": "",
    }
    issues: List[Dict[str, Any]] = []

    if not po_number:
        result["summary"] = "No PO specified on invoice header"
        agent_out = {
            "agent": "POMatchingAgent",
            "invoice_id": invoice_doc.get("_id"),
            "status": "not_found",
            "result": result,
            "next_agent": None,
            "score": 0.0,
            "errors": [],
            "timestamp": now
        }
        return agent_out

    # fetch PO from pos collection (we stored pos with _id = po_number earlier)
    po = db.get_collection("pos").find_one({"_id": po_number})
    if not po:
        # try lookup by po_number field if stored differently
        po = db.get_collection("pos").find_one({"po_number": po_number})

    if not po:
        result["summary"] = f"PO not found: {po_number}"
        agent_out = {
            "agent": "POMatchingAgent",
            "invoice_id": invoice_doc.get("_id"),
            "status": "not_found",
            "result": result,
            "next_agent": None,
            "score": 0.0,
            "errors": [],
            "timestamp": now
        }
        return agent_out

    result["po_found"] = True
    result["po_number"] = po_number

    # compute totals
    po_total = float(po.get("total", 0) or 0)
    inv_total = float(header.get("amount", 0) or 0)
    total_diff_pct = _pct_diff(po_total, inv_total)

    # build line matching by naive index or by description similarity (for now index)
    po_lines = po.get("lines", []) or []
    matched_lines = []
    tolerance_exceeded = False

    # iterate over invoice items and try to match to PO lines by index
    for idx, inv_item in enumerate(items):
        inv_amt = float(inv_item.get("amount", 0) or 0)
        po_line = po_lines[idx] if idx < len(po_lines) else None
        if po_line:
            po_amt = float(po_line.get("amount", 0) or 0)
            price_diff_pct = _pct_diff(po_amt, inv_amt)
            qty_diff_pct = 0.0
            # handle qty if present
            if "quantity" in po_line or "quantity" in inv_item:
                po_qty = float(po_line.get("quantity", 1) or 1)
                inv_qty = float(inv_item.get("quantity", 1) or 1)
                qty_diff_pct = _pct_diff(po_qty, inv_qty)
            status = "matched"
            if price_diff_pct > PRICE_TOL_PCT:
                status = "price_mismatch"
                tolerance_exceeded = True
            if qty_diff_pct > QTY_TOL_PCT:
                status = "qty_mismatch"
                tolerance_exceeded = True

            matched_lines.append({
                "po_line_index": idx+1,
                "item_index": idx,
                "po_amount": po_amt,
                "inv_amount": inv_amt,
                "price_diff_pct": price_diff_pct,
                "qty_diff_pct": qty_diff_pct,
                "status": status
            })
        else:
            # no corresponding PO line
            matched_lines.append({
                "po_line_index": None,
                "item_index": idx,
                "po_amount": None,
                "inv_amount": inv_amt,
                "price_diff_pct": None,
                "qty_diff_pct": None,
                "status": "no_po_line"
            })
            tolerance_exceeded = True

    # compute overall match_score (naive): proportion of lines matched with status 'matched'
    matched_count = sum(1 for m in matched_lines if m["status"] == "matched")
    total_lines = max(1, len(matched_lines))
    match_score = matched_count / total_lines

    result.update({
        "po_total": po_total,
        "invoice_total": inv_total,
        "total_diff_pct": total_diff_pct,
        "line_matches": matched_lines,
        "tolerance_exceeded": tolerance_exceeded,
        "match_score": match_score,
        "summary": f"PO found. total_diff_pct={total_diff_pct:.2f}, match_score={match_score:.2f}"
    })

    status = "matched" if (not tolerance_exceeded and total_diff_pct <= PRICE_TOL_PCT) else "partial_match"

    agent_out = {
        "agent": "POMatchingAgent",
        "invoice_id": invoice_doc.get("_id"),
        "status": status,
        "result": result,
        "next_agent": "CodingAgent" if status == "matched" else None,
        "score": match_score,
        "errors": [],
        "timestamp": now
    }
    return agent_out
