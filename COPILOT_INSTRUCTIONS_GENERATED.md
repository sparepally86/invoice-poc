# Copilot Instructions Generated

Successfully created `.github/copilot-instructions.md` with comprehensive guidance for AI agents working in this codebase.

## What's Included

### Architecture Overview
- **Project Purpose**: Invoice processing automation with agentic orchestration
- **Core Components**: API Layer, Orchestrator, Agent Pipeline, Storage Layer
- **Critical Data Structures**: Invoice lifecycle states, key MongoDB collections, ValidationResult contract

### Validation Rule Taxonomy (Step B Context)
- **Category definitions**: STRUCTURAL, FINANCIAL, POLICY, DUPLICATE
- **Severity rules**: HARD (blocking), SOFT (warning) with tolerance thresholds
- **Configuration**: Environment variables for tolerance and warning thresholds

### Orchestrator Workflow
- **Step-by-step processing**: Validation → PO Matching → Coding → Risk/Approval
- **Key pattern**: Synchronous agent execution in worker thread, MongoDB task queue polling
- **Human task creation**: Triggered when validation or matching fails

### Code Patterns & Conventions
- **Agent Response Format**: Standardized dict with agent name, status, timestamp
- **Persistence Patterns**: Workflow audit trail vs. structured results
- **Field Naming**: Consistent `header.` prefixes, array handling
- **Logging**: Centralized logger with structured context

### Testing & Development
- **Unit tests**: Validation contract, taxonomy, LLM behavior
- **Integration tests**: End-to-end workflows with real MongoDB
- **Commands**: How to run tests, start API, debug

### Design Decisions & Non-Goals
- **Why async background worker**: Scalability, non-blocking API
- **Why separate `invoice.validation` field**: Queryability, separation of concerns
- **Tolerance-based severity**: Configurable thresholds for risk management
- **Scope boundaries**: What's out of scope (branching, UI, dynamic config)

### Extension Guide
- **Adding validation rules**: Where to code, how to classify, testing approach
- **Adding agents**: Integration pattern, task creation, persistence
- **Modifying orchestrator**: Consistency requirements, helper functions

### Key Files
- **app/orchestrator.py** (426 lines) — Central coordination logic
- **app/agents/validation.py** (159 lines) — Validation rules and taxonomy
- **app/api/invoices.py** — Invoice lifecycle endpoints
- **app/storage/mongo_client.py** — Database schema and queries
- **IMPLEMENTATION_SUMMARY.md, VALIDATION_RESULT_GUIDE.md** — Reference docs

## Usage

This file is designed to:
1. **Onboard AI agents quickly** — No need to read full codebase to understand architecture
2. **Enforce consistency** — Patterns and conventions guide implementation decisions
3. **Prevent scope creep** — Clear boundaries on what's in/out of scope
4. **Guide extensions** — Step-by-step approach for adding features

Place guidance in your IDE's AI copilot settings or share with Claude/ChatGPT/etc. when working on this codebase.

## Feedback?

The instructions cover:
- ✓ Big picture architecture (data flow, component relationships)
- ✓ Developer workflows (testing, running services)
- ✓ Project-specific conventions (agent patterns, taxonomy rules)
- ✓ Integration points (orchestrator → agents, persistence patterns)
- ✓ Extension guide (how to add new rules, agents, or modify workflows)

**Unclear or incomplete sections?** Let me know which areas need more detail or clarification.
