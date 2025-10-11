# app/agents/explain.py
"""
ExplainAgent with Retrieval integration (Phase B step 008).

Behaviour:
- Builds a short query from invoice + triggering_step
- Calls RetrievalAgent.retrieve(query) to get top-K similar chunks
- Includes retrieved excerpts in the prompt sent to LLM
- Returns a canonical AgentResponse dict including ai.retrieval_hits and result.sources
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ai.llm_client import get_llm_client
from app.agents.retrieval import retrieve

AGENT_NAME = "ExplainAgent"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _make_query_text(invoice: Dict[str, Any], triggering_step: Dict[str, Any]) -> str:
    """
    Build a compact query string used for retrieval.
    Uses invoice reference, triggering reason, and first line description.
    """
    header = invoice.get("header", {}) or {}
    parts = []
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id")
    if invoice_ref:
        parts.append(str(invoice_ref))
    # prefer explicit reason/result text
    if triggering_step:
        if isinstance(triggering_step.get("result"), dict):
            parts.append(" ".join(map(str, triggering_step.get("result").values())))
        else:
            parts.append(str(triggering_step.get("result") or triggering_step.get("reason") or triggering_step.get("message") or ""))
    # include first line description for context
    lines = invoice.get("lines") or invoice.get("items") or []
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        if isinstance(first, dict):
            parts.append(str(first.get("description", "") or first.get("desc", "") or ""))
        else:
            parts.append(str(first))
    # join and trim
    q = " ".join([p for p in parts if p]).strip()
    # fallback: use invoice id
    if not q:
        q = str(invoice.get("_id", "invoice"))
    return q[:1000]


def _build_prompt(invoice: Dict[str, Any], triggering_step: Dict[str, Any], retrieval_hits: List[Dict[str, Any]]) -> str:
    """
    Construct a compact prompt that includes:
     - invoice reference
     - triggering reason
     - short invoice snippet
     - retrieved contexts (top 3) with excerpt
     - instruction asking for 1-3 sentence explanation + evidence + action suggestion
    """
    header = invoice.get("header", {}) or {}
    invoice_ref = header.get("invoice_ref") or header.get("invoice_number") or invoice.get("_id", "unknown")
    # triggering reason
    reason = ""
    if triggering_step:
        if isinstance(triggering_step.get("result"), dict):
            reason = json.dumps(triggering_step.get("result"))
        else:
            reason = str(triggering_step.get("result") or triggering_step.get("reason") or triggering_step.get("message") or "")
    # invoice snippet (first line)
    lines = invoice.get("lines") or invoice.get("items") or []
    snippet = ""
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        snippet = (first.get("description") if isinstance(first, dict) else str(first)) if first else ""
    # retrieved context block
    retrieved_text = ""
    if retrieval_hits:
        parts = []
        for r in retrieval_hits[:3]:
            # include id and short excerpt
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
        "evidence": [],   # populate later with structured evidence extraction
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


def run_explain(db: Any, invoice: Dict[str, Any], triggering_step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explain flow:
      1. build query and call RetrievalAgent.retrieve()
      2. build prompt including retrieval excerpts
      3. call LLM client (noop by default)
      4. return structured AgentResponse with retrieval_hits included
    """
    # 1) retrieval
    try:
        query = _make_query_text(invoice, triggering_step)
        retrieval_hits = retrieve(query, k=5, filter=None) or []
    except Exception:
        retrieval_hits = []

    # 2) build prompt (includes top-3 retrieved excerpts)
    prompt = _build_prompt(invoice, triggering_step, retrieval_hits)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    # 3) call LLM
    llm = get_llm_client()
    try:
        llm_resp = llm.call_llm(prompt, max_tokens=300, temperature=0.0)
        # Prefer parsed/raw fields if present (noop returns 'text')
        if isinstance(llm_resp, dict):
            explanation_text = None
            # prefer parsed -> raw if available
            parsed = llm_resp.get("parsed")
            if isinstance(parsed, dict) and parsed.get("raw"):
                explanation_text = parsed.get("raw")
            explanation_text = explanation_text or llm_resp.get("text") or llm_resp.get("raw") or str(llm_resp)
        else:
            explanation_text = str(llm_resp)
    except Exception as e:
        explanation_text = f"[explain_error]: {str(e)}"

    # 4) build response
    agent_response = _make_agent_response(explanation_text, retrieval_hits, prompt_hash)
    try:
        # coarse score: presence of retrieval_hits increases trust
        agent_response["score"] = 0.6 + 0.3 * (1 if retrieval_hits else 0)
    except Exception:
        agent_response["score"] = 0.5

    return agent_response
