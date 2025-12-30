# Step E3: Policy Validation Rules - Quick Reference

## At a Glance

Step E3 adds **4 new POLICY validation rules** that enforce business constraints:

| Rule | Checks | Severity | Status |
|------|--------|----------|--------|
| **E3-P1** | Allowed currency | HARD | FAIL |
| **E3-P2** | Invoice date window | HARD or SOFT | FAIL or WARN |
| **E3-P3** | High amount warning | SOFT | WARN |
| **E3-P4** | Country-specific fields | HARD | FAIL |

---

## The 4 Rules (Code Snippets)

### E3-P1: Allowed Currency
```python
allowed_currencies = ["INR", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]
if currency not in allowed_currencies:
    emit HARD issue
    # → Status: FAIL
```

**Rule**: Currency must be in allowed list  
**Severity**: Always HARD  
**Example Failure**: `currency = "XYZ"` → FAIL

---

### E3-P2: Invoice Date Window
```python
today = datetime.utcnow().date()

if invoice_date > today:
    emit HARD issue ("future date")      # → Status: FAIL
elif (today - invoice_date).days > 180:
    emit SOFT issue ("too old")          # → Status: WARN
```

**Rule**: Date must be today or past, but not older than 180 days  
**Severity**: HARD (future) or SOFT (too old)  
**Examples**:
- Future: `invoice_date = "2025-12-31"` (today is 12-30) → FAIL
- Too old: `invoice_date = "2025-05-01"` (243 days old) → WARN
- Valid: `invoice_date = "2025-12-20"` → PASS

---

### E3-P3: High Amount Threshold
```python
threshold = 1_000_000
if total_amount > threshold:
    emit SOFT issue
    # → Status: WARN (non-blocking)
```

**Rule**: Invoices above $1M require attention (warning only)  
**Severity**: Always SOFT (informational)  
**Example**: `total_amount = 2_000_000` → WARN (continues processing)

---

### E3-P4: Country-Specific Mandatory Fields
```python
if country == "IN":
    if not gstin:
        emit HARD issue  # → Status: FAIL
elif country == "US":
    if not tax_id:
        emit HARD issue  # → Status: FAIL
```

**Rule**:
- India (IN): Must have GSTIN
- US: Must have Tax ID
- Others: No requirement

**Severity**: Always HARD  
**Examples**:
- India with GSTIN: ✓ PASS
- India without GSTIN: ✗ FAIL
- US with Tax ID: ✓ PASS
- US without Tax ID: ✗ FAIL

---

## Status Determination

```python
# Status is determined by issue severity
if any_issue has severity == "HARD":
    status = "FAIL"
elif any_issue has severity == "SOFT":
    status = "WARN"
else:
    status = "PASS"
```

**Scenarios**:
- E3-P1 violation (HARD): `status = FAIL` → Exception
- E3-P2 future (HARD): `status = FAIL` → Exception
- E3-P2 old (SOFT): `status = WARN` → Validated (with warning)
- E3-P3 violation (SOFT): `status = WARN` → Validated (with warning)
- E3-P4 violation (HARD): `status = FAIL` → Exception

---

## Non-Configurable Values

| Item | Value | Notes |
|------|-------|-------|
| Allowed Currencies | 8 hardcoded | INR, USD, EUR, GBP, JPY, CAD, AUD, CHF |
| Date Window | 180 days | > 180 is SOFT warning |
| High Amount Threshold | 1,000,000 | Currency units |
| India Requirement | GSTIN mandatory | No fallback |
| US Requirement | Tax ID mandatory | No fallback |

All hard-coded in `_validate_policy_rules()`. Non-configurable in Step E3.

---

## File Locations

**Implementation**:
- `app/agents/validation_domain.py` → `_validate_policy_rules()` (lines ~354-550)

**Tests**:
- `test_step_e3_policy_rules.py` (500+ lines, 20 tests, 100% pass rate)

**Documentation**:
- `STEP_E3_IMPLEMENTATION.md` (this file plus detailed guide)

---

## Testing

```bash
# Run E3 tests
python test_step_e3_policy_rules.py
# Output: ✓ ALL STEP E3 TESTS PASSED (20/20)

# Verify backward compatibility
python test_step_e1_structural_rules.py
python test_step_e2_financial_rules.py
python test_orchestrator_branching.py
# All should PASS
```

---

## MongoDB Query Examples

### Find invoices with currency violations
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "UNSUPPORTED_CURRENCY",
      severity: "HARD"
    }
  }
})
```

### Find invoices with future dates (HARD failure)
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "INVALID_INVOICE_DATE",
      severity: "HARD",
      "metadata.days_in_future": { $gt: 0 }
    }
  }
})
```

### Find old invoices (SOFT warning)
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "INVALID_INVOICE_DATE",
      severity: "SOFT",
      "metadata.days_old": { $gt: 180 }
    }
  }
})
```

### Find high-value invoices
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "HIGH_VALUE_INVOICE",
      severity: "SOFT"
    }
  }
})
```

### Find missing country compliance fields
```javascript
db.invoices.find({
  "validation.issues": {
    $elemMatch: {
      code: "MISSING_COUNTRY_MANDATORY_FIELD",
      severity: "HARD"
    }
  }
})
```

---

## For Developers: Adding a New Policy Rule

1. **Open** `app/agents/validation_domain.py`
2. **Find** `_validate_policy_rules()` function (line ~354)
3. **Add** your rule logic after existing E3 rules
4. **Emit** issue with all required fields:
   ```python
   issues.append({
       "code": "YOUR_RULE_CODE",
       "category": "POLICY",
       "severity": "HARD" or "SOFT",
       "field": "header.field_name",
       "message": "Clear description",
       "metadata": {
           "key": "value",
           ...
       }
   })
   ```
5. **Test** by adding test case to `test_step_e3_policy_rules.py`

---

## Orchestrator Integration

```
Orchestrator
├─ Receive invoice in RECEIVED state
├─ Run ValidationAgent
│  └─ ValidationDomain
│     ├─ E1 STRUCTURAL rules
│     ├─ E2 FINANCIAL rules
│     └─ E3 POLICY rules ← NEW
│
├─ Check status
│  ├─ FAIL → Create EXCEPTION task
│  └─ WARN or PASS → Continue to POMatchingAgent
│
└─ Continue workflow
```

**No orchestrator changes** — E3 plugs into existing validation pipeline.

---

## Backward Compatibility

✅ **E1 Structural Rules** — Still passing (no changes)  
✅ **E2 Financial Rules** — Still passing (no changes)  
✅ **Step D Orchestrator** — Still passing (no changes)  
✅ **Vendor Check** — Preserved in E3 (enhanced, not modified)

---

## Status: COMPLETE

✅ 4 rules implemented  
✅ 20 tests passing  
✅ Backward compatible  
✅ Documented  
✅ Production ready

**What's Next**: E4 (Duplicate Rules), E5 (Configuration), E6 (Approvals)
