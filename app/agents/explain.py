# app/agents/explain.py
"""
ExplainAgent with RAG (Retrieval-Augmented Generation), PII redaction, telemetry, and rate limiting.

Behavior:
- If RAG_ENABLED: call RetrievalAgent.search_invoice() to get relevant prior cases
- Construct RAG prompt with system/user messages
- Redact PII from prompt
- Enforce simple rate limit for LLM calls
- Call the LLM with the redacted prompt
- Capture token usage and latency; store telemetry into workflow step (if TELEMETRY_WRITE=true)
- Return AgentResponse including retrieval_hits with proper metadata
"""

import hashlib
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from openai import OpenAI as _OpenAI

from app.ai.llm_client import get_llm_client
from app.agents.retrieval import search_invoice
from app.ai.llm_rate_limiter import get_rate_limiter
from app.config import RAG_ENABLED, RETRIEVAL_K_DEFAULT, TELEMETRY_WRITE
from app.utils.pii_redaction import redact_pii

logger = logging.getLogger(__name__)

AGENT_NAME = "ExplainAgent"
TELEMETRY_ENABLED = TELEMETRY_WRITE  # Alias for clarity

# RAG System message - fixed instruction for grounding explanations
RAG_SYSTEM_MESSAGE = """You are an AP automation assistant. Explain invoice issues clearly and factually.
Base your explanation only on the provided validation results and retrieved evidence.
If evidence is insufficient, say so explicitly."""


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


# -----------------------
# prompt & retrieval
# -----------------------
def _extract_invoice_context(invoice: Dict[str, Any]) -> str:
    """
    Extract a short summary of invoice context for the RAG prompt.
    Includes: vendor, amount, PO/non-PO status.
    Uses internal invoice ID (_id), not vendor's invoice number.
    """
    header = invoice.get("header", {}) or {}
    parts = []
    
    # Use internal invoice ID first (most important); fall back to vendor's invoice_number only if no ID
    invoice_ref = invoice.get("_id") or header.get("invoice_ref") or header.get("invoice_number") or "unknown"
    parts.append(f"Invoice: {invoice_ref}")
    
    vendor = header.get("vendor") or header.get("vendor_name") or header.get("supplier")
    if vendor:
        parts.append(f"Vendor: {vendor}")
    
    amount = header.get("amount") or header.get("total") or header.get("invoice_amount")
    if amount:
        parts.append(f"Amount: {amount}")
    
    po_number = header.get("po_number") or header.get("po") or header.get("po_reference")
    if po_number:
        parts.append(f"PO: {po_number}")
    else:
        parts.append("Type: Non-PO invoice")
    
    return ", ".join(parts)


def _extract_validation_results(triggering_step: Dict[str, Any]) -> str:
    """
    Extract validation results (codes + messages) from the triggering step.
    """
    if not triggering_step:
        return "No validation details available."
    
    result = triggering_step.get("result", {})
    if isinstance(result, dict):
        codes = result.get("codes") or result.get("validation_codes") or []
        messages = result.get("messages") or result.get("validation_messages") or []
        errors = result.get("errors") or []
        
        parts = []
        if codes:
            parts.append(f"Codes: {', '.join(str(c) for c in codes[:5])}")
        if messages:
            parts.append(f"Messages: {'; '.join(str(m)[:100] for m in messages[:3])}")
        if errors:
            parts.append(f"Errors: {'; '.join(str(e)[:100] for e in errors[:3])}")
        
        if parts:
            return " | ".join(parts)
        
        return json.dumps(result)[:500]
    
    return str(result)[:500] if result else "Validation triggered without specific details."


def _extract_validation_result_from_dict(validation_result: Dict[str, Any]) -> str:
    """
    Extract validation results directly from ValidationResult dict (not triggering_step).
    This is the NEW method used in Step G for grounded explanations.
    
    Args:
        validation_result: ValidationResult dict with structure:
            {
              "status": "PASS" | "WARN" | "FAIL",
              "issues": [...],
              "summary": {...}
            }
    
    Returns:
        Formatted string of validation issues for inclusion in LLM prompt
    """
    if not validation_result:
        return "No validation details available."
    
    if not isinstance(validation_result, dict):
        return str(validation_result)[:500]
    
    issues = validation_result.get("issues", [])
    summary = validation_result.get("summary", {})
    
    parts = []
    parts.append(f"Validation Status: {validation_result.get('status', 'UNKNOWN')}")
    
    if summary:
        hard_failures = summary.get("hard_failures", 0)
        soft_warnings = summary.get("soft_warnings", 0)
        if hard_failures > 0:
            parts.append(f"Hard Failures: {hard_failures}")
        if soft_warnings > 0:
            parts.append(f"Soft Warnings: {soft_warnings}")
    
    if issues:
        parts.append(f"\nIssues ({len(issues)} total):")
        for issue in issues[:10]:  # Limit to first 10 issues
            code = issue.get("code", "UNKNOWN")
            category = issue.get("category", "UNKNOWN")
            severity = issue.get("severity", "UNKNOWN")
            message = issue.get("message", "No message")[:100]
            field = issue.get("field", "")
            
            field_str = f" [{field}]" if field else ""
            parts.append(f"  - {code} ({category}/{severity}){field_str}: {message}")
    
    return "\n".join(parts)


def _format_retrieved_evidence(retrieval_hits: List[Dict[str, Any]], k: int = 3) -> str:
    """
    Format retrieved evidence for the RAG prompt.
    Limits to top K hits and truncates text_preview.
    
    If no strong similar cases are found (empty retrieval_hits list after relevance filtering),
    returns explicit message indicating no precedent cases exist.
    """
    if not retrieval_hits:
        return "No prior similar cases found in the knowledge base. This appears to be a novel pattern without precedent."
    
    parts = ["Retrieved prior cases with sufficient similarity:"]
    for hit in retrieval_hits[:k]:
        hit_id = hit.get("id", "unknown")
        score = hit.get("score", 0.0)
        metadata = hit.get("metadata", {}) or {}
        
        doc_type = metadata.get("type", "doc")
        text_preview = metadata.get("text_preview", "")[:150]
        
        type_label = f"[{doc_type}]"
        parts.append(f"- {type_label} {hit_id} (score={score:.2f}): {text_preview}")
    
    return "\n".join(parts)


def _build_rag_user_message(invoice: Dict[str, Any], triggering_step: Dict[str, Any], retrieval_hits: List[Dict[str, Any]], k: int = 3) -> str:
    """
    Build the RAG user message with:
    - Short summary of invoice context (vendor, amount, PO / non-PO)
    - Validation results (codes + messages)
    - Retrieved evidence section
    """
    context = _extract_invoice_context(invoice)
    validation = _extract_validation_results(triggering_step)
    evidence = _format_retrieved_evidence(retrieval_hits, k=k)
    
    user_message = f"""Invoice Context:
{context}

Validation Results:
{validation}

{evidence}

Task: In 1-3 sentences, explain why the system flagged this invoice. List explicit evidence pointers (e.g., line indices, field names) and suggest a concrete action the reviewer can take to resolve it."""
    
    return user_message


def _build_combined_prompt(system_message: str, user_message: str) -> str:
    """
    Combine system and user messages into a single prompt for LLM clients
    that don't support separate system/user messages.
    """
    return f"{system_message}\n\n---\n\n{user_message}"


def _make_agent_response(
    explanation_text: str,
    retrieval_hits: List[Dict[str, Any]],
    prompt_hash: str,
    model: str,
    tokens: Optional[Dict[str, int]] = None,
    latency_ms: Optional[int] = None,
    telemetry: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build the ExplainAgent response with proper metadata structure.
    
    Args:
        explanation_text: The generated explanation
        retrieval_hits: List of retrieval hits with normalized format
        prompt_hash: SHA256 hash of the prompt (first 16 chars)
        model: LLM model name used
        tokens: Token usage dict with prompt/completion counts (if available)
        latency_ms: Wall-clock latency of LLM call in milliseconds (if available)
        telemetry: Complete telemetry dict to include in result.ai.telemetry (if TELEMETRY_WRITE=true)
    """
    now = _now_iso()
    result = {
        "explanation_text": explanation_text,
        "evidence": [],
        "actions": [],
        "sources": retrieval_hits
    }
    
    ai_metadata = {
        "retrieval_hits": retrieval_hits or [],
        "prompt_hash": prompt_hash,
        "model": model
    }
    if tokens:
        ai_metadata["tokens"] = tokens
    
    # Include telemetry in workflow step if TELEMETRY_WRITE=true
    if TELEMETRY_ENABLED and telemetry:
        ai_metadata["telemetry"] = telemetry
    
    agent_resp = {
        "agent": AGENT_NAME,
        "status": "completed",
        "result": result,
        "next_agent": None,
        "score": 0.0,
        "timestamp": now,
        "ai": ai_metadata
    }
    return agent_resp


def _generate_grounded_explanations(
    llm,
    invoice: Dict[str, Any],
    validation_result: Dict[str, Any],
    retrieval_hits: List[Dict[str, Any]],
    rate_limiter,
    redacted_by: Optional[str] = None
) -> tuple[List[Dict[str, Any]], Optional[int], Optional[Dict[str, Any]]]:
    """
    Generate LLM-based explanations for each validation issue.
    
    Step G implementation: Ground explanations directly on validation issues.
    - Iterates over validation_result.issues
    - For each issue, generates a specific explanation tied to that issue
    - Returns issue_explanations array + optional latency_ms + telemetry dict
    
    Args:
        llm: LLM client instance
        invoice: Invoice document
        validation_result: ValidationResult dict with status, issues[], summary
        retrieval_hits: Retrieved similar cases from knowledge base
        rate_limiter: Rate limiter instance
        redacted_by: Optional string describing what was redacted
    
    Returns:
        Tuple of (issue_explanations, latency_ms, telemetry_dict)
        - issue_explanations: List of dicts with:
            {
              "rule_code": "...",
              "category": "...",
              "severity": "...",
              "explanation": "..."
            }
        - latency_ms: Total wall-clock latency or None if skipped/failed
        - telemetry_dict: Optional telemetry object
    """
    issue_explanations = []
    if not validation_result or not validation_result.get("issues"):
        return issue_explanations, None, None
    
    issues = validation_result.get("issues", [])
    context = _extract_invoice_context(invoice)
    evidence = _format_retrieved_evidence(retrieval_hits, k=3)
    
    total_latency_ms = 0
    telemetry_dict = None
    
    # Rate limiting check
    invoice_id = invoice.get("_id")
    if rate_limiter and not rate_limiter.allow_request(invoice_id=invoice_id):
        logger.warning("ExplainAgent rate-limited; skipping grounded explanations")
        return issue_explanations, None, None
    
    for issue_index, issue in enumerate(issues):
        rule_code = issue.get("code", "UNKNOWN")
        category = issue.get("category", "UNKNOWN")
        severity = issue.get("severity", "UNKNOWN")
        field = issue.get("field", "")
        message = issue.get("message", "")
        
        # Build prompt for this specific issue
        issue_user_message = f"""Invoice Context:
{context}

Validation Issue:
Rule: {rule_code} ({category}/{severity})
Field: {field}
Message: {message}

{evidence}

Task: In 1-2 sentences, explain this specific validation issue. Reference the field name, explain why it's problematic, and suggest how to fix it. Be concrete and factual."""
        
        # Build full prompt
        full_prompt = _build_combined_prompt(RAG_SYSTEM_MESSAGE, issue_user_message)
        prompt_hash = hashlib.sha256(full_prompt.encode()).hexdigest()[:16]
        
        # Redact PII
        redacted_prompt = redact_pii(full_prompt)
        
        # Call LLM with timing
        llm_start_time = time.time()
        try:
            llm_resp = llm.call_llm(redacted_prompt, max_tokens=150, temperature=0.0)
            latency_ms = int((time.time() - llm_start_time) * 1000)
            total_latency_ms += latency_ms
            
            # Extract explanation text
            explanation_text = ""
            if isinstance(llm_resp, dict):
                parsed = llm_resp.get("parsed")
                if isinstance(parsed, dict) and parsed.get("raw"):
                    explanation_text = parsed.get("raw")
                else:
                    explanation_text = llm_resp.get("text") or llm_resp.get("raw") or str(llm_resp)
            else:
                explanation_text = str(llm_resp)
            
            # Build issue explanation entry
            issue_explanation = {
                "rule_code": rule_code,
                "category": category,
                "severity": severity,
                "explanation": explanation_text.strip()
            }
            issue_explanations.append(issue_explanation)
            
            logger.debug("[issue=%s] Generated explanation: %s", rule_code, explanation_text[:100])
            
        except Exception as e:
            latency_ms = int((time.time() - llm_start_time) * 1000)
            total_latency_ms += latency_ms
            logger.exception("Failed to generate explanation for issue %s: %s", rule_code, str(e))
            
            # Still add entry with error message
            issue_explanation = {
                "rule_code": rule_code,
                "category": category,
                "severity": severity,
                "explanation": f"[Unable to generate explanation: {str(e)}]"
            }
            issue_explanations.append(issue_explanation)
    
    # Build telemetry
    if TELEMETRY_ENABLED:
        telemetry_dict = {
            "issue_explanations_generated": len(issue_explanations),
            "total_latency_ms": total_latency_ms,
            "issues_count": len(issues)
        }
    
    return issue_explanations, total_latency_ms, telemetry_dict


# -----------------------
# run_explain (main)
# -----------------------
def run_explain(db: Any, invoice: Dict[str, Any], triggering_step: Dict[str, Any], validation_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    RAG-enabled ExplainAgent flow with retrieval, redaction, rate limiting and telemetry logging.
    
    Step G (Grounding): 
    - If validation_result provided, generates grounded explanations per validation issue
    - Each explanation tied to a specific rule_code from ValidationResult.issues[]
    - No hallucinated issues - only explains what ValidationResult contains
    
    Fallback (legacy):
    - If validation_result not provided, falls back to old behavior with triggering_step
    
    Args:
        db: MongoDB client
        invoice: Invoice document
        triggering_step: Original triggering step (for backward compatibility)
        validation_result: ValidationResult dict with issues (NEW in Step G)
    
    Returns:
        AgentResponse dict with:
        - If grounding enabled: result.issue_explanations[] with rule_code, category, severity, explanation
        - If legacy: result.explanation_text (single explanation)
    """
    llm = get_llm_client()
    model_name = getattr(llm, "model", "noop") or "noop"
    k = RETRIEVAL_K_DEFAULT
    invoice_id = invoice.get("_id")
    
    # 1) RAG retrieval (if enabled)
    retrieval_hits: List[Dict[str, Any]] = []
    if RAG_ENABLED:
        try:
            retrieval_hits = search_invoice(invoice, k=k, min_score=0.0) or []
        except Exception:
            retrieval_hits = []
    
    # 2) NEW IN STEP G: Use validation_result if provided (grounded explanations)
    if validation_result and isinstance(validation_result, dict) and validation_result.get("issues"):
        logger.info("[invoice_id=%s] Using grounded explanation generator for %d issues", 
                   invoice_id, len(validation_result.get("issues", [])))
        
        # Get rate limiter
        rl = get_rate_limiter()
        
        # Generate grounded explanations per issue
        issue_explanations, total_latency_ms, grounded_telemetry = _generate_grounded_explanations(
            llm, invoice, validation_result, retrieval_hits, rl
        )
        
        # Build overall summary from all explanations
        overall_summary = f"Validation found {len(validation_result.get('issues', []))} issue(s):"
        
        # Build response with issue_explanations
        now = _now_iso()
        result = {
            "overall_summary": overall_summary,
            "issue_explanations": issue_explanations,
            "sources": retrieval_hits
        }
        
        ai_metadata = {
            "retrieval_hits": retrieval_hits or [],
            "model": model_name,
            "grounding_enabled": True,
            "issue_count": len(issue_explanations)
        }
        
        if grounded_telemetry:
            ai_metadata["telemetry"] = grounded_telemetry
        
        agent_response = {
            "agent": AGENT_NAME,
            "status": "completed",
            "result": result,
            "next_agent": None,
            "score": 0.7,  # Higher score for grounded explanations
            "timestamp": now,
            "ai": ai_metadata
        }
        
        return agent_response
    
    # 3) FALLBACK: Legacy behavior if no validation_result or validation_result is empty
    logger.debug("[invoice_id=%s] Falling back to legacy explanation mode", invoice_id)
    
    # Build prompt based on RAG mode
    if RAG_ENABLED:
        user_message = _build_rag_user_message(invoice, triggering_step, retrieval_hits, k=k)
        prompt = _build_combined_prompt(RAG_SYSTEM_MESSAGE, user_message)
    else:
        context = _extract_invoice_context(invoice)
        validation = _extract_validation_results(triggering_step)
        prompt = f"""Invoice Context:
{context}

Validation Results:
{validation}

Task: In 1-3 sentences, explain why the system flagged this invoice. List explicit evidence pointers (e.g., line indices, field names) and suggest a concrete action the reviewer can take to resolve it."""
    
    # CRITICAL: Redact PII BEFORE computing hash and before LLM call
    # Pass invoice to redact vendor identifiers from context
    redacted_prompt = redact_pii(prompt, invoice=invoice)
    
    # Compute prompt_hash on REDACTED prompt for telemetry integrity
    prompt_hash = hashlib.sha256(redacted_prompt.encode("utf-8")).hexdigest()[:16]
    
    # Log redaction completion (debug level to avoid noise in production)
    if prompt != redacted_prompt:
        logger.debug(f"ExplainAgent: PII redacted for invoice {invoice.get('_id')}. "
                    f"Original length: {len(prompt)}, Redacted length: {len(redacted_prompt)}, "
                    f"Prompt hash: {prompt_hash}")
    else:
        logger.debug(f"ExplainAgent: No PII detected in prompt for invoice {invoice.get('_id')}. "
                    f"Prompt hash: {prompt_hash}")

    # 4) Rate limiting
    rl = get_rate_limiter()
    if not rl.allow_request(invoice_id=invoice_id):
        logger.warning(
            f"ExplainAgent: Rate limit exceeded for invoice_id={invoice_id}. "
            f"Returning fallback explanation."
        )
        try:
            telemetry = {
                "agent": AGENT_NAME,
                "invoice_id": invoice_id,
                "prompt_hash": prompt_hash,
                "model": model_name,
                "event": "rate_limited",
                "timestamp": _now_iso(),
                "retrieval_hits_count": len(retrieval_hits),
                "rag_enabled": RAG_ENABLED
            }
            try:
                db.telemetry.insert_one(telemetry)
            except Exception:
                pass
        except Exception:
            pass
        
        now = _now_iso()
        return {
            "agent": AGENT_NAME,
            "status": "rate_limited",
            "result": {
                "explanation_text": "Explanation skipped due to rate limits.",
                "evidence": [],
                "actions": [],
                "sources": retrieval_hits
            },
            "next_agent": None,
            "score": 0.0,
            "timestamp": now,
            "ai": {
                "prompt_hash": prompt_hash,
                "retrieval_hits": retrieval_hits,
                "model": model_name,
                "rate_limited": True
            }
        }

    # 5) Call LLM with latency measurement
    llm_start_time = time.time()
    latency_ms = None
    try:
        llm_resp = llm.call_llm(redacted_prompt, max_tokens=300, temperature=0.0)
        latency_ms = int((time.time() - llm_start_time) * 1000)
    except Exception as e:
        latency_ms = int((time.time() - llm_start_time) * 1000)
        
        try:
            telemetry = {
                "agent": AGENT_NAME,
                "invoice_id": invoice_id,
                "prompt_hash": prompt_hash,
                "model": model_name,
                "event": "llm_error",
                "error": str(e),
                "timestamp": _now_iso(),
                "retrieval_hits_count": len(retrieval_hits),
                "rag_enabled": RAG_ENABLED
            }
            try:
                db.telemetry.insert_one(telemetry)
            except Exception:
                pass
        except Exception:
            pass
        
        explanation_text = f"[explain_error]: {str(e)}"
        agent_response = _make_agent_response(
            explanation_text, retrieval_hits, prompt_hash, model_name, tokens=None
        )
        agent_response["status"] = "failed"
        return agent_response

    # 6) Extract explanation text from LLM response
    explanation_text = ""
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

    # 7) Extract token usage (prefer provider-provided usage)
    tokens: Optional[Dict[str, int]] = None
    try:
        if isinstance(llm_resp, dict):
            usage = llm_resp.get("usage") or (llm_resp.get("meta", {}) or {}).get("usage")
            if usage:
                tokens = {
                    "prompt": usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0)
                }
            else:
                approx = int((len(redacted_prompt) + len(explanation_text or "")) / 4)
                tokens = {"prompt": approx, "completion": 0}
    except Exception:
        tokens = {"prompt": len(redacted_prompt) // 4, "completion": 0}

    # 8) Build telemetry dict for workflow step (if TELEMETRY_WRITE=true)
    telemetry_dict: Optional[Dict[str, Any]] = None
    if TELEMETRY_ENABLED:
        try:
            total_tokens = 0
            if tokens:
                total_tokens = tokens.get("prompt", 0) + tokens.get("completion", 0)
            
            telemetry_dict = {
                "prompt_hash": prompt_hash,
                "model": model_name,
                "token_usage": {
                    "prompt_tokens": tokens.get("prompt", 0) if tokens else None,
                    "completion_tokens": tokens.get("completion", 0) if tokens else None,
                    "total_tokens": total_tokens if tokens else None
                },
                "latency_ms": latency_ms,
                "retrieval_count": len(retrieval_hits)
            }
            if invoice_id:
                telemetry_dict["invoice_id"] = invoice_id
            
            logger.debug("ExplainAgent telemetry: prompt_hash=%s model=%s latency_ms=%s retrieval_count=%d",
                        prompt_hash, model_name, latency_ms, len(retrieval_hits))
        except Exception as e:
            logger.exception("Failed to build telemetry dict: %s", str(e))
            # Telemetry is optional; don't break if it fails
            telemetry_dict = None

    # 9) Persist telemetry to DB (best-effort, legacy location)
    try:
        telemetry = {
            "agent": AGENT_NAME,
            "invoice_id": invoice_id,
            "prompt_hash": prompt_hash,
            "model": model_name,
            "tokens": tokens,
            "timestamp": _now_iso(),
            "retrieval_hits_count": len(retrieval_hits),
            "event": "explain_called",
            "rag_enabled": RAG_ENABLED
        }
        try:
            db.telemetry.insert_one(telemetry)
        except Exception:
            pass
    except Exception:
        pass

    # 10) Build response with proper metadata including new telemetry
    agent_response = _make_agent_response(
        explanation_text, retrieval_hits, prompt_hash, model_name, 
        tokens=tokens, latency_ms=latency_ms, telemetry=telemetry_dict
    )
    
    # Score higher if we have retrieval hits (RAG grounded)
    try:
        agent_response["score"] = 0.6 + 0.3 * (1 if retrieval_hits else 0)
    except Exception:
        agent_response["score"] = 0.5

    return agent_response


def _chat(model: str, messages: list, temperature: float = 0.2, timeout: int = 30) -> str:
    """
    Direct OpenAI chat completion helper using v1+ SDK.
    Note: For most use cases, prefer using get_llm_client().call_llm() instead.
    """
    client = _OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    return resp.choices[0].message.content or ""
