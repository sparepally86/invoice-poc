# app/agents/explain.py
"""
ExplainAgent with PII redaction, telemetry, and rate limiting.

Behavior:
- Build query and retrieval hits
- Construct prompt and redact PII
- Enforce simple rate limit for LLM calls
- Call the LLM with the redacted prompt
- Estimate/capture token usage and store telemetry into db.telemetry
- Return AgentResponse including retrieval_hits
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ai.llm_client import get_llm_client
from app.agents.retrieval import retrieve
from app.storage.mongo_client import get_db
from app.ai.llm_rate_limiter import get_rate_limiter

AGENT_NAME = "ExplainAgent"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


# -----------------------
# PII redaction utilities
# -----------------------
# This is a conservative regex-based redaction applied to prompt text before sending to LLM.
# It is intentionally simple — improve rules and add allowlists/denylists for production.
_EMAIL_RE = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{6,12}(?!\d)")
_LONG_DIGIT_RE = re.compile(r"\b\d{9,}\b")  # long runs of digits (IDs, etc.)
_CREDITCARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")  # naive cc pattern

def redact_text(text: str) -> str:
    if not text:
        return text
    s = str(text)
    s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = _CREDITCARD_RE.sub("[REDACTED_CC]", s)
    s = _PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = _LONG_DIGIT_RE.sub("[REDACTED_ID]", s)
    return s


# -----------------------
# prompt & retrieval
# -----------------------
def _make_query_text(invoice: Dict[str, Any], triggering_step: Dict[str, Any]) -> str:
    header = invoice.get("header", {}) or {}
    parts = []
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id")
    if invoice_ref:
        parts.append(str(invoice_ref))
    if triggering_step:
        if isinstance(triggering_step.get("result"), dict):
            parts.append(" ".join(map(str, triggering_step.get("result").values())))
        else:
            parts.append(str(triggering_step.get("result") or triggering_step.get("reason") or triggering_step.get("message") or ""))
    lines = invoice.get("lines") or invoice.get("items") or []
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        if isinstance(first, dict):
            parts.append(str(first.get("description", "") or first.get("desc", "") or ""))
        else:
            parts.append(str(first))
    q = " ".join([p for p in parts if p]).strip()
    if not q:
        q = str(invoice.get("_id", "invoice"))
    return q[:1000]


def _build_prompt(invoice: Dict[str, Any], triggering_step: Dict[str, Any], retrieval_hits: List[Dict[str, Any]]) -> str:
    header = invoice.get("header", {}) or {}
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id", "unknown")
    reason = ""
    if triggering_step:
        if isinstance(triggering_step.get("result"), dict):
            reason = json.dumps(triggering_step.get("result"))
        else:
            reason = str(triggering_step.get("result") or triggering_step.get("reason") or triggering_step.get("message") or "")
    lines = invoice.get("lines") or invoice.get("items") or []
    snippet = ""
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        snippet = (first.get("description") if isinstance(first, dict) else str(first)) if first else ""
    retrieved_text = ""
    if retrieval_hits:
        parts = []
        for r in retrieval_hits[:3]:
            eid = r.get("id") or r.get("doc_id") or r.get("chunk_id") or "id"
            score = r.get("score")
            excerpt = r.get("excerpt") or (r.get("metadata", {}).get("chunk_text_preview") if r.get("metadata") else None) or ""
            parts.append(f"- {eid} (score={score}): {excerpt[:240]}")
        retrieved_text = "\nSimilar cases:\n" + "\n".join(parts)
    prompt = (
        f"Invoice: {invoice_ref}\n"
        f"Trigger: {reason}\n"
        f"Snippet: {snippet}\n\n"
        f"{retrieved_text}\n\n"
        "Task: In 1-3 sentences, explain why the system flagged this invoice (concise). "
        "Then list explicit evidence pointers (e.g., line indices, field names) and suggest a small, concrete action the reviewer can take to resolve it.\n\n"
        "Respond in plain text only."
    )
    return prompt


def _make_agent_response(explanation_text: str, retrieval_hits: List[Dict[str, Any]], prompt_hash: str) -> Dict[str, Any]:
    now = _now_iso()
    result = {
        "explanation": explanation_text,
        "evidence": [],
        "actions": [],
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


# -----------------------
# run_explain (main)
# -----------------------
def run_explain(db: Any, invoice: Dict[str, Any], triggering_step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explain flow with retrieval, redaction, rate limiting and telemetry logging.
    """
    # 1) retrieval
    try:
        query = _make_query_text(invoice, triggering_step)
        retrieval_hits = retrieve(query, k=5, filter=None) or []
    except Exception:
        retrieval_hits = []

    # 2) build prompt and redaction
    prompt = _build_prompt(invoice, triggering_step, retrieval_hits)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    redacted_prompt = redact_text(prompt)

    # 3) rate limiting
    rl = get_rate_limiter()
    # cost can be tuned; default cost 1 per call
    if not rl.allow_request(cost=1.0):
        # log telemetry event for rate-limited attempt
        try:
            telemetry = {
                "agent": AGENT_NAME,
                "invoice_id": invoice.get("_id"),
                "prompt_hash": prompt_hash,
                "model": (get_llm_client().model if getattr(get_llm_client(), "model", None) else "noop"),
                "event": "rate_limited",
                "timestamp": _now_iso(),
                "retrieval_hits_count": len(retrieval_hits)
            }
            # best-effort persist
            try:
                db.telemetry.insert_one(telemetry)
            except Exception:
                pass
        except Exception:
            pass
        # return a short AgentResponse indicating rate limit
        now = _now_iso()
        return {
            "agent": AGENT_NAME,
            "status": "rate_limited",
            "result": {"message": "rate limit exceeded, please retry later"},
            "next_agent": None,
            "score": 0.0,
            "timestamp": now,
            "ai": {"prompt_hash": prompt_hash, "retrieval_hits": retrieval_hits}
        }

    # 4) call LLM
    llm = get_llm_client()
    try:
        llm_resp = llm.call_llm(redacted_prompt, max_tokens=300, temperature=0.0)
    except Exception as e:
        # log telemetry for error
        try:
            telemetry = {
                "agent": AGENT_NAME,
                "invoice_id": invoice.get("_id"),
                "prompt_hash": prompt_hash,
                "model": getattr(llm, "model", "unknown"),
                "event": "llm_error",
                "error": str(e),
                "timestamp": _now_iso(),
                "retrieval_hits_count": len(retrieval_hits)
            }
            try:
                db.telemetry.insert_one(telemetry)
            except Exception:
                pass
        except Exception:
            pass
        explanation_text = f"[explain_error]: {str(e)}"
        agent_response = _make_agent_response(explanation_text, retrieval_hits, prompt_hash)
        agent_response["status"] = "failed"
        return agent_response

    # 5) extract explanation text from llm_resp
    explanation_text = None
    try:
        if isinstance(llm_resp, dict):
            parsed = llm_resp.get("parsed")
            if isinstance(parsed, dict) and parsed.get("raw"):
                explanation_text = parsed.get("raw")
            else:
                explanation_text = llm_resp.get("text") or llm_resp.get("raw") or str(llm_resp)
        else:
            explanation_text = str(llm_resp)
    except Exception:
        explanation_text = str(llm_resp)

    # 6) estimate token usage (prefer provider-provided usage)
    usage = None
    try:
        if isinstance(llm_resp, dict) and llm_resp.get("usage"):
            usage = llm_resp.get("usage")
        else:
            # conservative estimate: (prompt chars + response chars) / 4 -> tokens
            approx_tokens = int((len(redacted_prompt) + len(explanation_text or "")) / 4)
            usage = {"approx_tokens": approx_tokens}
    except Exception:
        usage = {"approx_tokens": len(redacted_prompt) // 4}

    # 7) persist telemetry to DB (best-effort)
    try:
        telemetry = {
            "agent": AGENT_NAME,
            "invoice_id": invoice.get("_id"),
            "prompt_hash": prompt_hash,
            "model": getattr(llm, "model", None),
            "usage": usage,
            "timestamp": _now_iso(),
            "retrieval_hits_count": len(retrieval_hits),
            "event": "explain_called"
        }
        try:
            db.telemetry.insert_one(telemetry)
        except Exception:
            pass
    except Exception:
        pass

    # 8) build response
    agent_response = _make_agent_response(explanation_text, retrieval_hits, prompt_hash)
    try:
        agent_response["score"] = 0.6 + 0.3 * (1 if retrieval_hits else 0)
    except Exception:
        agent_response["score"] = 0.5

    return agent_response
