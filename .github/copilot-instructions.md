# Copilot Instructions for Invoice POC (Agentic AP)

## Project Overview
Invoice processing automation system using agentic orchestration. FastAPI backend with async task queue, MongoDB persistence, and multi-agent pipeline for validation, matching, coding, and approval.

## Architecture & Data Flow

### Core Components
1. **API Layer** (`app/api/invoices.py`, `tasks.py`) — HTTP endpoints for invoice submission and retrieval
2. **Orchestrator** (`app/orchestrator.py`) — Async background worker that polls MongoDB `tasks` collection and processes invoices through agent pipeline
3. **Agents** (`app/agents/`) — Deterministic processing logic:
   - `validation.py` — Structural, financial, policy checks → emits structured `ValidationResult` to `invoice.validation`
   - `po_match.py` — Matches invoice to purchase orders
   - `coding.py` / `coding_nonpo.py` — GL account assignment (PO-matched vs standalone)
   - `risk.py` — Auto-approval or escalation decisions
   - `explain.py` — LLM-based reasoning for manual review
4. **Storage** (`app/storage/mongo_client.py`) — MongoDB client for invoices and tasks

### Critical Data Structures

**Invoice Lifecycle States:**
```
DRAFT → RECEIVED → VALIDATED → [MATCHED/EXCEPTION] → CODED → [PENDING_APPROVAL/READY_FOR_POSTING] → POSTED
```

**Key Collections:**
- `invoices` — Document per invoice (identity, header, lines, validation result, workflow steps)
- `tasks` — Work queue with statuses: `queued`, `processing`, `done`, `error`
- `vendors` — Master data
- `pos` — Purchase orders

**ValidationResult Contract** (stored at `invoice.validation`):
```python
{
  "status": "PASS" | "WARN" | "FAIL",
  "issues": [
    {
      "code": "MISSING_FIELD" | "VENDOR_NOT_FOUND" | "AMOUNT_MISMATCH",
      "category": "STRUCTURAL" | "FINANCIAL" | "POLICY" | "DUPLICATE",
      "severity": "HARD" | "SOFT",
      "field": "header.field_name",
      "message": "Human-readable explanation",
      "metadata": {"optional": "context"}
    }
  ],
  "summary": {"hard_failures": int, "soft_warnings": int},
  "validated_at": "ISO-8601 timestamp"
}
```

## Validation Rule Taxonomy (Step B)

- **STRUCTURAL**: Schema/format violations → Always HARD
- **FINANCIAL**: Amount consistency → SOFT if ≤2% diff, HARD if >2%
- **POLICY**: Business rules (vendor eligibility, date constraints) → HARD or SOFT per policy
- **DUPLICATE**: Risk protection → HARD (mostly)

Tolerance thresholds set via environment:
- `VALIDATION_AMOUNT_TOLERANCE_PCT` (default 0.5%) — Emit issue only if exceeded
- `VALIDATION_AMOUNT_WARNING_THRESHOLD_PCT` (default 2.0%) — Threshold between SOFT/HARD

## Orchestrator Workflow

**Per-Task Processing** (`process_task`):
1. Load invoice, normalize structure
2. **ValidationAgent** — Validate structure/financial/policy
   - Persist `ValidationResult` to `invoice.validation`
   - If HARD failures → create `human_review` task, exit early
   - Otherwise continue
3. **POMatchingAgent** (if PO present) — Match to PO
   - If mismatch → create `human_review` task, exit early
4. **CodingAgent** (if PO matched) — Assign GL accounts
   - Emit to workflow steps
5. **RiskApprovalAgent** — Auto-approve or escalate
   - If auto_approve → mark `READY_FOR_POSTING`
   - If needs human → create `approval` task
6. Mark invoice `READY_FOR_POSTING` if no human tasks created

**Key Pattern:** Agents run synchronously in worker thread via `asyncio.to_thread()`. Any blocking MongoDB call is wrapped this way. Agent outputs are persisted to `invoice._workflow.steps` (audit trail) and structured results (like `validation`) to top-level fields.

## Code Patterns & Conventions

### Agent Response Format
Every agent returns a dict via `ensure_agent_response()`:
```python
{
  "agent": "AgentName",
  "invoice_id": "...",
  "status": "completed" | "needs_human" | "failed",
  "result": {...},  # Agent-specific payload
  "timestamp": "ISO-8601",
  # Optional:
  "validation": {...},  # ValidationResult (only ValidationAgent)
  "next_agent": "AgentName"
}
```

### Persistence Patterns
- **Workflow audit trail**: All agent outputs → `db.invoices.update_one(..., {"$push": {"_workflow.steps": output}})`
- **Structured results**: Canonical objects → `db.invoices.update_one(..., {"$set": {"validation": result}})` (ValidationResult)
- **Status updates**: Use centralized helper `update_invoice_status(db, invoice_id, status, source, note)`

### Field Naming & Normalization
- Invoice header uses `header.` prefix (e.g., `header.invoice_number`, `header.total_amount`)
- Lines array at top level: `lines[].line_amount`, `lines[].description`
- Utility `ensure_minimal_structure(invoice)` normalizes nested documents

### Logging
Use centralized logger from `app.logging_config`:
```python
from app.logging_config import get_logger
logger = get_logger(__name__)
logger.info("[task_id=%s invoice_id=%s] Processing...", task_id, invoice_id)
```

## Testing & Workflows

### Unit Tests (No Server)
- `test_validation_contract.py` — ValidationResult structure
- `test_taxonomy_simple.py` — Rule classification
- `test_llm_client.py` — LLM rate limiting
- `test_vector_client.py` — Vector store operations

### Integration Tests (Requires API)
- `integration_test_real.py` — End-to-end workflow with real MongoDB
- `test_invoice_lifecycle.py` — State transitions
- `demo_rate_limiting.py` — Rate limiting behavior

### Running Tests
```bash
# Start API first (if integration test)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Run unit tests (separate terminal)
python test_validation_contract.py
python test_taxonomy_simple.py

# Run integration tests
python integration_test_real.py
```

## Critical Design Decisions

1. **Orchestrator as Background Worker** — Avoids blocking API calls. Tasks poll from MongoDB `tasks` collection (simple, scales horizontally)
2. **ValidationResult Persisted at `invoice.validation`** — Queryable, separates concerns (workflow steps vs. canonical result)
3. **Tolerance-Based FINANCIAL Severity** — 0.5% issues ignored, 0.5-2% is SOFT warning, >2% is HARD failure (configurable)
4. **No Validation Branching in Orchestrator** — Validation failure creates human task; orchestrator logic unchanged (semantic equivalence with Step A)
5. **Explain Agent Post-Hoc** — Only triggered if human review needed, runs synchronously for audit trail

## Non-Goals (Scope Boundaries)

- ❌ No orchestration branching based on validation status (future: Step C)
- ❌ No UI rendering of validation results (future: Step D)
- ❌ No dynamic rule configuration (future: Step E)
- ❌ No MatchingAgent/CodingAgent refactoring (isolated to validation rules)

## Extending the System

### Adding a New Validation Rule
1. Add logic in `app/agents/validation.py` — `run_validation()` function
2. Classify: category (STRUCTURAL|FINANCIAL|POLICY|DUPLICATE), severity (HARD|SOFT)
3. Emit structured issue with `code`, `category`, `severity`, `field`, `message`, `metadata`
4. Test: add case to `test_taxonomy_simple.py`

### Adding a New Agent
1. Create `app/agents/new_agent.py` — implement `run_new_agent(db, invoice)`
2. Return agent response via `ensure_agent_response("NewAgent", {...})`
3. Integrate in `app/orchestrator.py` — add `await asyncio.to_thread(run_new_agent, db, invoice)`
4. Persist result: `db.invoices.update_one(..., {"$push": {"_workflow.steps": agent_output}})`

### Modifying Orchestrator Logic
1. Edit `process_task()` in `app/orchestrator.py`
2. Maintain status update consistency: always call `update_invoice_status()` via centralized helper
3. Ensure new tasks (approval, human_review, etc.) follow dict structure in existing code
4. Update tests: `test_invoice_lifecycle.py`

## Environment Variables

**Required:**
- `MONGODB_URI` — Connection string
- `MONGODB_DB` — Database name
- `LLM_PROVIDER` — "noop", "openai", "local"
- `OPENAI_API_KEY` — If using OpenAI

**Optional (Validation):**
- `VALIDATION_AMOUNT_TOLERANCE_PCT` (default 0.5)
- `VALIDATION_AMOUNT_WARNING_THRESHOLD_PCT` (default 2.0)

**Optional (Rate Limiting):**
- `LLM_RATE_LIMIT_REQUESTS` — Requests per window
- `LLM_RATE_LIMIT_WINDOW_SEC` — Time window

## Key Files to Read First

1. `app/orchestrator.py` (426 lines) — Understand task processing and agent sequencing
2. `app/agents/validation.py` (159 lines) — Understand validation rules and taxonomy
3. `app/api/invoices.py` (first 100 lines) — Understand invoice intake and lifecycle
4. `app/storage/mongo_client.py` — Understand MongoDB schema and queries
5. `IMPLEMENTATION_SUMMARY.md` / `VALIDATION_RESULT_GUIDE.md` — Reference for Step A/B details
