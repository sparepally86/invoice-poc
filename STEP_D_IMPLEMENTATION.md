# Step D: Orchestrator Branching Implementation

## Overview
Implemented explicit branching in the orchestrator based on `ValidationResult.status` to enable intelligent routing:
- **PASS**: Continue normally to MatchingAgent
- **WARN**: Continue to MatchingAgent with warnings retained (non-blocking)
- **FAIL**: Stop orchestration, transition to EXCEPTION state, skip all downstream agents

## Implementation Details

### Location
File: `app/orchestrator.py` (lines 157-204)
Section: "STEP D: ORCHESTRATOR BRANCHING ON VALIDATION RESULT STATUS"

### Core Logic

```python
# After ValidationResult is persisted at invoice.validation,
# branch based on validation status
validation_status = validation_result.get("status") if validation_result else "UNKNOWN"

if validation_status == "FAIL":
    # Hard blocking issues detected - stop orchestration
    logger.info(
        "[task_id=%s invoice_id=%s] ValidationResult.status=FAIL: Stopping orchestration",
        task["_id"], invoice_id
    )
    await update_invoice_status(
        db, invoice_id, "EXCEPTION", "Orchestrator",
        note=f"Validation failed: {summary.get('hard_failures', 0)} hard failures"
    )
    await db.tasks.update_one(
        {"_id": task["_id"]},
        {"$set": {"status": "done", "finished_at": datetime.utcnow()}}
    )
    return  # Skip MatchingAgent and all downstream agents

elif validation_status == "WARN":
    # Soft warnings only - continue with warning note
    logger.info(
        "[task_id=%s invoice_id=%s] ValidationResult.status=WARN: Continuing with warnings",
        task["_id"], invoice_id
    )
    await update_invoice_status(
        db, invoice_id, "VALIDATED", "Orchestrator",
        note=f"Validation passed with {summary.get('soft_warnings', 0)} soft warnings"
    )
    # Continue to MatchingAgent (no return statement)

elif validation_status == "PASS":
    # No issues detected - proceed normally
    logger.info(
        "[task_id=%s invoice_id=%s] ValidationResult.status=PASS: Proceeding normally",
        task["_id"], invoice_id
    )
    await update_invoice_status(
        db, invoice_id, "VALIDATED", "Orchestrator",
        note="Validation passed successfully"
    )
    # Continue to MatchingAgent (no return statement)

# MatchingAgent is now conditionally reached based on validation_status
if validation_status != "FAIL":
    matching_out = await asyncio.to_thread(run_po_match, db, invoice)
    # ... rest of pipeline
```

### Branching Rules

| Status | Action | Invoice Status | Continue? | Downstream |
|--------|--------|---|-----------|-----------|
| **PASS** | Continue normally | VALIDATED | Yes | All agents run |
| **WARN** | Continue with warnings | VALIDATED | Yes | All agents run (warnings in context) |
| **FAIL** | Stop processing | EXCEPTION | No | MatchingAgent & downstream SKIPPED |

### Data Preservation

- **ValidationResult**: Persisted to `invoice.validation` BEFORE branching decision
- **Issues**: All validation issues (HARD and SOFT) retained for human review
- **Warnings**: Available in invoice workflow context for downstream agents
- **Workflow Trail**: All branching decisions logged to `invoice._workflow.steps`

### Status Transitions

```
RECEIVED -> VALIDATION -> [Branch Point]
                           |
                    ┌──────┼──────┐
                    |      |      |
                 PASS    WARN   FAIL
                    |      |      |
                 VALIDATED|   EXCEPTION
                    |      |
              [Continue] [Stop]
                    |
            -> MATCHED/EXCEPTION (PO logic)
            -> CODED
            -> PENDING_APPROVAL/READY_FOR_POSTING
            -> POSTED
```

### Error Handling

- **UNKNOWN Status**: If validation_result is missing or status is not recognized, continues as PASS (safe default)
- **Task Cleanup**: Failed validation tasks are marked "done" in the task queue to prevent reprocessing
- **Audit Trail**: All branching decisions logged with task_id and invoice_id for traceability

## Design Decisions

### 1. Early Return for FAIL
```python
return  # Exit orchestrator immediately for FAIL
```
- **Why**: Prevents accidental MatchingAgent invocation
- **Safety**: Explicit guard against downstream processing
- **Simplicity**: Clear intent - orchestration stops here

### 2. Conditional Statements vs. Jump Tables
```python
if validation_status == "FAIL": ...
elif validation_status == "WARN": ...
elif validation_status == "PASS": ...
```
- **Why**: Explicit, readable, easy to debug
- **vs. Alternative**: Jump tables would be less maintainable in this context
- **Maintainability**: Clear responsibility per status

### 3. ValidationResult Persistence Before Branching
```python
# Persist FIRST (line ~165)
await asyncio.to_thread(
    db.invoices.update_one,
    {"_id": invoice_id},
    {"$set": {"validation": validation_result}}
)

# THEN branch (line 157+)
validation_status = validation_result.get("status")
if validation_status == "FAIL": ...
```
- **Why**: Ensures data is available even if orchestration stops
- **Data Integrity**: No loss of validation information
- **Human Review**: All validation issues accessible for manual intervention

### 4. Non-Blocking WARN Behavior
```python
elif validation_status == "WARN":
    # Continue (no return)
    # MatchingAgent sees warnings in context
```
- **Why**: Soft warnings should not block automation
- **Business Logic**: Validation doesn't prevent progress
- **Context Awareness**: Downstream agents aware of warnings

## Testing & Validation

### Test File
Location: `test_orchestrator_branching.py`

### Test Coverage

**TEST 1: PASS Path**
- Verify PASS status routes to MatchingAgent
- Verify invoice marked VALIDATED
- Verify no issues detected

**TEST 2: WARN Path**
- Verify WARN status routes to MatchingAgent
- Verify invoice marked VALIDATED with warning note
- Verify soft warnings retained in workflow

**TEST 3: FAIL Path**
- Verify FAIL status stops orchestration
- Verify invoice moved to EXCEPTION
- Verify MatchingAgent NOT called
- Verify early return executed

**TEST 4: Status Transitions**
- PASS -> VALIDATED
- WARN -> VALIDATED (with note)
- FAIL -> EXCEPTION

**TEST 5: Branching Logic**
- All three if/elif branches reachable
- Early return guards against downstream

**TEST 6: Real-World Scenarios**
- Valid invoice (0 issues) -> PASS
- Minor discrepancy (1% diff, within tolerance) -> WARN
- Missing field -> FAIL
- Vendor not found -> FAIL
- Large amount diff (5%) -> FAIL

**TEST 7: Backward Compatibility**
- No new invoice states introduced
- MatchingAgent, CodingAgent unchanged
- RiskApprovalAgent unchanged
- No approval workflows added
- No new services created

### Test Results
```
TEST 1: PASS Path                         [OK]
TEST 2: WARN Path                         [OK]
TEST 3: FAIL Path                         [OK]
TEST 4: Branching Decision Logic          [OK]
TEST 5: Orchestrator Code Implementation  [OK]
TEST 6: Real-World Scenarios              [OK]
TEST 7: Backward Compatibility            [OK]

ALL TESTS PASSED: 7/7
```

## Code Changes Summary

### Modified Files
- `app/orchestrator.py`: Lines 157-204 (48 lines added, 39 lines removed, net +9)

### New Files
- `test_orchestrator_branching.py`: 290+ lines, comprehensive test suite

### Unchanged Components
- ValidationDomain (Step C)
- ValidationAgent
- MatchingAgent
- CodingAgent
- RiskApprovalAgent
- Invoice status definitions
- Task queue logic
- Database schema

## Non-Goals (Out of Scope)

✗ New invoice statuses (using existing VALIDATED, EXCEPTION)
✗ Approval workflow changes
✗ MatchingAgent/CodingAgent refactoring
✗ UI rendering (handled in future Step D)
✗ Dynamic rule configuration (handled in future Step E)
✗ New services, events, or queues

## Integration Points

### Upstream (Input)
- **ValidationDomain**: Provides ValidationResult with status (PASS/WARN/FAIL)
- **Validation Issues**: Structured issues with category, severity, field, message

### Downstream (Output)
- **MatchingAgent**: Only invoked if validation_status != FAIL
- **CodingAgent**: Only reached if MatchingAgent runs
- **RiskApprovalAgent**: Only reached if CodingAgent runs
- **Invoice Status**: Updated based on validation outcome

## Deployment Checklist

- [x] Code changes implemented and tested
- [x] Branching logic verified (PASS/WARN/FAIL)
- [x] FAIL path stops orchestration
- [x] Early return prevents downstream agents
- [x] ValidationResult persisted before branching
- [x] Status transitions correct
- [x] Test suite created and passing (7/7)
- [x] Backward compatibility verified
- [x] Logging includes task_id and invoice_id
- [x] Documentation complete

## Troubleshooting

### "UNKNOWN" Status Appearing
- **Cause**: ValidationResult missing or status field undefined
- **Solution**: Check validation_result structure, ensure ValidationDomain returns status
- **Fallback**: System treats UNKNOWN as PASS (continues normally)

### MatchingAgent Still Called for FAIL
- **Cause**: Branching logic not reached
- **Debug**: Check orchestrator line 157+, verify if/elif present
- **Verify**: Confirm orchestrator.py actually modified (git diff app/orchestrator.py)

### Test Failures
- **Setup**: Ensure MongoDB is running and accessible
- **Dependencies**: Verify all validation rules in ValidationDomain implemented
- **Status Values**: Confirm ValidationResult.status values are "PASS", "WARN", or "FAIL"

## Future Extensions

**Step E (Dynamic Rule Configuration)**
- Add capability to enable/disable rules via configuration
- Branch logic remains unchanged - only rule evaluation changes

**Step C+ (Additional Orchestration)**
- Add conditional steps based on PO match results
- Branch logic remains unchanged - new branches added

**Step D+ (UI Rendering)**
- Display branching decisions in UI
- Orchestrator logic remains unchanged

## References

- [Step C: ValidationDomain Refactor](STEP_C_IMPLEMENTATION.md)
- [Step B: Validation Rule Taxonomy](VALIDATION_RESULT_GUIDE.md)
- [Step A: ValidationResult Contract](VALIDATION_RESULT_GUIDE.md#validation-result-contract)
- [Architecture Overview](README.md#architecture--data-flow)
