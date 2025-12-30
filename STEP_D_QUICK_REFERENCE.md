# Step D: Orchestrator Branching - Quick Reference

## At a Glance

Step D implements explicit routing in the orchestrator based on validation outcomes:

```
Validation Result → [PASS] → Continue normally
                  → [WARN] → Continue with warnings
                  → [FAIL] → STOP (move to EXCEPTION)
```

## Key Changes

### 1. Where
**File**: `app/orchestrator.py`  
**Lines**: 157-204 (branching logic after validation)

### 2. What
After ValidationResult is persisted, orchestrator checks `validation_result.get("status")`:

```python
if validation_status == "FAIL":
    # Stop orchestration, mark EXCEPTION
    return

elif validation_status == "WARN":
    # Continue (non-blocking warnings)
    
elif validation_status == "PASS":
    # Continue normally
```

### 3. Why
- **FAIL**: Hard blocking issues (structural errors, vendor not found, >2% amount mismatch)
- **WARN**: Soft warnings only (0.5-2% amount discrepancy) - automation continues
- **PASS**: No issues - proceed normally

## Branching Table

| Input Status | Action | Output Status | MatchingAgent? |
|---|---|---|---|
| FAIL | Stop | EXCEPTION | ❌ No |
| WARN | Continue | VALIDATED | ✅ Yes |
| PASS | Continue | VALIDATED | ✅ Yes |

## For Developers

### To Understand Branching
1. Open `app/orchestrator.py` line 157
2. See PASS/WARN/FAIL handling
3. FAIL case has `return` - skips downstream
4. WARN/PASS cases continue normally

### To Add Another Branch
```python
elif validation_status == "NEW_STATUS":
    # Your logic here
    if should_skip_downstream:
        return
```

### To Debug Status Flow
```python
logger.info(
    "[task_id=%s invoice_id=%s] ValidationResult.status=%s",
    task["_id"], invoice_id, validation_status
)
```

## Data Flow

```
[Validation]
    ↓
[Persist ValidationResult at invoice.validation]
    ↓
[Read validation_status]
    ↓
    ├─→ FAIL: Update status→EXCEPTION, return (stop)
    │
    ├─→ WARN: Update status→VALIDATED (warn note), continue
    │
    └─→ PASS: Update status→VALIDATED, continue
        ↓
    [MatchingAgent] (only if not FAIL)
        ↓
    [CodingAgent]
        ↓
    [RiskApprovalAgent]
```

## Testing

**Test File**: `test_orchestrator_branching.py`

Run all tests:
```bash
python test_orchestrator_branching.py
```

Results:
- TEST 1: PASS path ✓
- TEST 2: WARN path ✓
- TEST 3: FAIL path ✓
- TEST 4: Status transitions ✓
- TEST 5: Branching logic ✓
- TEST 6: Real scenarios ✓
- TEST 7: Backward compatibility ✓

## Status Impact

### Invoice Status Transitions
```
RECEIVED
    ↓
VALIDATION
    ↓
    ├─→ FAIL → EXCEPTION (stop)
    │
    └─→ PASS/WARN → VALIDATED (continue)
        ↓
    MATCHED/EXCEPTION (PO logic)
        ↓
    CODED
        ↓
    PENDING_APPROVAL/READY_FOR_POSTING
        ↓
    POSTED
```

## Backward Compatibility

✓ No new invoice states  
✓ No changes to validation logic  
✓ No changes to downstream agents  
✓ No changes to API endpoints  
✓ Existing tasks continue working  
✓ All Step A, B, C tests still pass  

## What Didn't Change

- ValidationDomain (Step C)
- Validation rules (Step B)
- ValidationResult contract (Step A)
- MatchingAgent behavior
- CodingAgent behavior
- RiskApprovalAgent behavior
- Task queue logic
- Database schema

## Common Questions

**Q: What happens if validation_status is missing?**  
A: Treated as PASS (continues normally) - safe default

**Q: Can WARN block automation?**  
A: No - WARN is non-blocking, MatchingAgent runs

**Q: Do WARN issues get logged?**  
A: Yes - persisted to invoice.validation, visible in workflow

**Q: Can FAIL be overridden?**  
A: No - FAIL always stops, no bypass logic

**Q: How do humans review FAIL invoices?**  
A: Via EXCEPTION state and future manual review UI (Step D)

## Implementation Checklist

- [x] Branching logic on validation_status
- [x] FAIL case stops orchestration (early return)
- [x] WARN case continues normally
- [x] PASS case continues normally
- [x] Status transitions correct
- [x] ValidationResult persisted before branching
- [x] All downstream agents conditionally skipped
- [x] Test suite comprehensive (7 test categories)
- [x] Backward compatibility verified
- [x] Documentation complete

## Code Snippet Reference

### Check Current Status
```python
validation_status = validation_result.get("status")
logger.info("Validation status: %s", validation_status)
```

### Branch Decision
```python
if validation_status == "FAIL":
    return  # Stop here
elif validation_status in ["WARN", "PASS"]:
    # Continue below
```

### Update Invoice Status
```python
await update_invoice_status(
    db, invoice_id,
    "EXCEPTION" if validation_status == "FAIL" else "VALIDATED",
    "Orchestrator",
    note=f"Validation outcome: {validation_status}"
)
```

## Files Modified in Step D

| File | Lines | Change |
|------|-------|--------|
| `app/orchestrator.py` | 157-204 | Added branching logic |
| `test_orchestrator_branching.py` | NEW | Test suite (290+ lines) |
| `STEP_D_IMPLEMENTATION.md` | NEW | Detailed documentation |

## Validation Status Values

- **PASS**: No issues detected
- **WARN**: Only soft warnings (0.5-2% discrepancies)
- **FAIL**: Hard blocking issues (>2%, missing fields, vendor errors)

## Related Steps

- **Step A**: Defined ValidationResult structure
- **Step B**: Defined rule taxonomy (PASS/WARN/FAIL logic)
- **Step C**: Implemented validation logic in ValidationDomain
- **Step D**: Orchestrator branching on validation outcomes (current)
- **Step E**: Dynamic rule configuration (future)

## Deployment Notes

- No database schema changes
- No service restarts required
- No API endpoint changes
- Fully backward compatible
- Can be deployed to production immediately
- No coordination with other systems needed

## Support & Debugging

For issues with branching:
1. Check orchestrator.py lines 157-204
2. Verify validation_status values (should be PASS, WARN, or FAIL)
3. Confirm return statement present in FAIL case (line ~202)
4. Run test_orchestrator_branching.py to verify behavior
5. Check logs for "[task_id=X invoice_id=Y] ValidationResult.status=Z"
