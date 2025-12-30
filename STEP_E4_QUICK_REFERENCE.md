# Step E4: Duplicate & Risk Validation Rules - Quick Reference

## At a Glance

Step E4 adds **3 new DUPLICATE validation rules** that detect double payments and suspicious patterns:

| Rule | Checks | Window | Tolerance | Severity |
|------|--------|--------|-----------|----------|
| **E4-D1** | Exact duplicate (vendor + invoice #) | N/A | Exact | HARD |
| **E4-D2** | Same amount, same vendor | 30 days | $0.00 | SOFT |
| **E4-D3** | Similar amount (vendor + amount) | 60 days | ±2% | SOFT |

---

## The 3 Rules (Quick Reference)

### E4-D1: Exact Duplicate
```python
if vendor_id == existing_vendor AND invoice_number == existing_number:
    emit HARD issue  # → Status: FAIL
```

**Rule**: Same vendor + same invoice number = duplicate  
**Severity**: Always HARD  
**Example**: VND-001 + INV-100 already exists → FAIL

---

### E4-D2: Time-Window Duplicate
```python
if vendor_id == existing_vendor AND total_amount == existing_amount:
    if invoice_date within last 30 days:
        emit SOFT issue  # → Status: WARN
```

**Rule**: Same vendor + same amount within 30 days  
**Severity**: Always SOFT  
**Example**: VND-001, $1000, 5 days ago, same vendor $1000 today → WARN

---

### E4-D3: Similar Amount Heuristic
```python
if vendor_id == existing_vendor AND amount_within_2_percent:
    if invoice_date within last 60 days:
        emit SOFT issue  # → Status: WARN
```

**Rule**: Same vendor + amount within ±2% in 60 days  
**Severity**: Always SOFT  
**Tolerance**: 2% (e.g., $1000 ± $20 = $980-$1020)  
**Example**: VND-001, $1010 similar to $1000 (1% diff, 10 days ago) → WARN

---

## Status Outcomes

```
E4-D1 (HARD) → Status = FAIL → EXCEPTION (stop)
E4-D2 (SOFT) → Status = WARN → VALIDATED (continue with warning)
E4-D3 (SOFT) → Status = WARN → VALIDATED (continue with warning)
```

---

## Non-Configurable Values

| Item | Value | Notes |
|------|-------|-------|
| E4-D1 Match | Exact (vendor + number) | 100% match required |
| E4-D2 Window | 30 days | Hard-coded |
| E4-D2 Amount | Exact match ($0.00 tolerance) | Hard-coded |
| E4-D3 Window | 60 days | Hard-coded |
| E4-D3 Tolerance | ±2.0% | Hard-coded |

---

## File Locations

**Implementation**:
- `app/agents/validation_domain.py` → `_validate_duplicate_rules()` (lines ~531-780)

**Tests**:
- `test_step_e4_duplicate_rules.py` (600+ lines, 15 tests, 100% pass)

**Documentation**:
- `STEP_E4_IMPLEMENTATION.md` (detailed guide)
- `STEP_E4_QUICK_REFERENCE.md` (this file)

---

## Testing

```bash
# Run E4 tests
python test_step_e4_duplicate_rules.py
# Output: [OK] ALL STEP E4 TESTS PASSED (15/15)

# Verify import
python -c "from app.agents.validation_domain import _validate_duplicate_rules; print('OK')"
```

---

## MongoDB Query Examples

### Find exact duplicates
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "DUPLICATE_INVOICE_EXACT",
      severity: "HARD"
    }
  }
})
```

### Find time-window duplicates
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "DUPLICATE_INVOICE_TIME_WINDOW",
      severity: "SOFT"
    }
  }
})
```

### Find similar amount warnings
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "SIMILAR_INVOICE_AMOUNT",
      "metadata.pct_difference": { $lte: 2.0 }
    }
  }
})
```

---

## Practical Examples

### Example 1: Exact Duplicate (FAIL)
```
Existing: VND-001, INV-100, $1000
New:      VND-001, INV-100, $1000
↓
E4-D1 → HARD → FAIL (exception)
```

### Example 2: Time-Window Duplicate (WARN)
```
Existing: VND-001, INV-100, $1000 (5 days ago)
New:      VND-001, INV-101, $1000 (today)
↓
E4-D2 → SOFT → WARN (continues with warning)
```

### Example 3: Similar Amount (WARN)
```
Existing: VND-001, INV-100, $1000 (10 days ago)
New:      VND-001, INV-101, $1010 (today)  [1% diff]
↓
E4-D3 → SOFT → WARN (continues with warning)
```

### Example 4: Legitimate Recurring (PASS)
```
Month 1: VND-001, INV-JAN, $5000
Month 2: VND-001, INV-FEB, $5200  [4% increase]
↓
No E4-D1 (different numbers)
No E4-D2 (different amounts)
No E4-D3 (>2% difference)
↓
Status = PASS
```

---

## For Developers: Adding a New Duplicate Rule

1. **Open** `app/agents/validation_domain.py`
2. **Find** `_validate_duplicate_rules()` function
3. **Add** your detection logic (e.g., vendor invoice history)
4. **Emit** issue:
   ```python
   issues.append({
       "code": "YOUR_RULE_CODE",
       "category": "DUPLICATE",
       "severity": "HARD" or "SOFT",
       "field": "header.field_name",
       "message": "Clear message",
       "metadata": {...}
   })
   ```
5. **Test** by adding case to `test_step_e4_duplicate_rules.py`

---

## Orchestrator Integration

```
Orchestrator processes invoice
  ├─ ValidationAgent.run_validation()
  │  ├─ Structural rules
  │  ├─ Financial rules
  │  ├─ Policy rules
  │  └─ Duplicate rules (E4-D1/D2/D3) ← NEW
  │
  └─ Check status
     ├─ FAIL → Stop (create exception task)
     └─ WARN/PASS → Continue (with warnings if WARN)
```

---

## Backward Compatibility

✓ **E1 Structural** — No changes  
✓ **E2 Financial** — No changes  
✓ **E3 Policy** — No changes  
✓ **Step D Orchestrator** — No changes  
✓ **Imports** — E4 imports without errors

---

## Status: COMPLETE

✓ 3 rules implemented  
✓ 15 tests passing  
✓ MongoDB queries integrated  
✓ Non-configurable defaults  
✓ Production ready

**What's Next**: E5 (Configuration), E6 (Approvals)
