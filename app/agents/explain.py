# app/agents/explain.py
"""
ExplainAgent scaffold (Phase B).

Provides:
  run_explain(db, invoice, triggering_step) -> AgentResponse (dict)

This is intentionally simple: it uses the noop LLM client and in-memory
vector client when real services aren't configured.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List

from app.ai.llm_client import get_llm_client
from app.storage.vector_client import get_vector_client

AGENT_NAME = "ExplainAgent"

def _now_iso():
    return datetime.utcnow().isoformat() + "Z"

def _prompt_from_context(invoice: Dict[str, Any], triggering_step: Dict[str, Any], retrieval_hits: List[Dict[str, Any]] = None) -> str:
    """
    Build a compact prompt from the invoice and triggering step.
    This prompt is intentionally short — we will expand sophistication later.
    """
    header = invoice.get("header", {})
    inv_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id", "unknown")
    reason = triggering_step.get("result") or triggering_step.get("reason") or triggering_step.get("message") or str(triggering_step)
    snippet = ""
    lines = invoice.get("lines") or invoice.get("items") or []
    if isinstance(lines, list) and len(lines) > 0:
        # include first line description for context
        first = lines[0]
        snippet = first.get("description", "") if isinstance(first, dict) else str(first)
    retrieval_part = ""
    if retrieval_hits:
        sources = []
        for r in retrieval_hits[:3]:
            sources.append(f"{r.get('id')} (score={r.get('score')})")
        retrieval_part = "\n\nSimilar cases: " + ", ".join(sources)
    prompt = (
        f"Invoice: {inv_ref}\n"
        f"Trigger: {reason}\n"
        f"First line: {snippet}\n\n"
        f"Please provide a short, actionable explanation in 1-3 sentences, and list evidence (line indices or fields) and a small action suggestion.\n"
        f"{retrieval_part}\n\nRespond in plain text."
    )
    return prompt

def _make_agent_response(explanation_text: str, retrieval_hits: List[Dict[str, Any]], prompt_hash: str) -> Dict[str, Any]:
    """
    Build canonical AgentResponse dictionary.
    """
    now = _now_iso()
    result = {
        "explanation": explanation_text,
        "evidence": [],   # simple for scaffold, populate with structured items later
        "actions": [],    # suggested edits / actions
        "sources": retrieval_hits
    }
    agent_resp = {
        "agent": AGENT_NAME,
        "status": "completed",
        "result": result,
        "next_agent": None,
        "score": 0.0,
        "timestamp": now,
        "ai": {
            "llm_model": get_llm_client().model,
            "prompt_hash": prompt_hash,
            "retrieval_hits": retrieval_hits or []
        }
    }
    return agent_resp

def run_explain(db: Any, invoice: Dict[str, Any], triggering_step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a simple explanation flow:
      1. Do a small retrieval using invoice text
      2. Build a prompt and call LLM client (noop by default)
      3. Return an AgentResponse-like dict
    """
    try:
        vc = get_vector_client()
    except Exception:
        vc = None

    retrieval_hits = []
    try:
        # Build a small query from header + triggering message
        header = invoice.get("header", {})
        query_parts = []
        if header.get("invoice_ref"):
            query_parts.append(str(header.get("invoice_ref")))
        if triggering_step.get("result"):
            query_parts.append(str(triggering_step.get("result")))
        # fallback: include first line text
        lines = invoice.get("lines") or invoice.get("items") or []
        if isinstance(lines, list) and len(lines):
            first = lines[0]
            if isinstance(first, dict):
                query_parts.append(first.get("description",""))
            else:
                query_parts.append(str(first))
        query_text = " ".join([p for p in query_parts if p])
        if vc and query_text:
            retrieval_hits = vc.search(query_text, k=5)
    except Exception:
        retrieval_hits = []

    # Build prompt and call LLM (noop typically)
    prompt = _prompt_from_context(invoice, triggering_step, retrieval_hits=retrieval_hits)
    # compute prompt hash for telemetry and caching
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    llm = get_llm_client()
    try:
        llm_resp = llm.call_llm(prompt, max_tokens=256, temperature=0.0)
        # for noop provider, llm_resp contains 'text' with echo
        explanation_text = None
        if isinstance(llm_resp, dict):
            # prefer parsed/parsed['raw'] or 'text'
            explanation_text = llm_resp.get("parsed", {}).get("raw") if isinstance(llm_resp.get("parsed"), dict) else llm_resp.get("text") or llm_resp.get("raw")
            if isinstance(explanation_text, dict):
                explanation_text = json.dumps(explanation_text)
        if not explanation_text:
            explanation_text = "[No explanation generated]"
    except Exception as e:
        explanation_text = f"[explain_error]: {str(e)}"

    # Build agent response
    agent_response = _make_agent_response(explanation_text, retrieval_hits, prompt_hash)
    # set a coarse score: if retrieval hits exist, boost score
    try:
        agent_response["score"] = 0.6 + 0.3 * (1 if retrieval_hits else 0)
    except Exception:
        agent_response["score"] = 0.5

    return agent_response
