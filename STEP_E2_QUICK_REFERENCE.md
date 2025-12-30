# Step E2: Financial Validation Rules - Quick Reference

## At a Glance

Step E2 adds **4 new FINANCIAL validation rules** with **fixed $1.00 tolerance**:

| Rule | Checks | Tolerance | Severity |
|------|--------|-----------|----------|
| **E2-F1** | Header total vs line sum | $1.00 absolute | SOFT/HARD |
| **E2-F2** | Tax total consistency | $1.00 absolute | SOFT/HARD |
| **E2-F3** | Discount math | N/A | SOFT (always) |
| **E2-F4** | Credit memo signs | Zero | HARD (always) |

This is the **first step introducing WARN outcomes** (SOFT severity issues).

---

## The Rules

### E2-F1: Total vs Line Sum Mismatch
```python
# Exact match → PASS
header.total_amount = 1000.0
lines sum = 1000.0

# Small diff ($0.50 within $1.00 tolerance) → WARN
header.total_amount = 1000.50
lines sum = 1000.0

# Large diff ($5.00 exceeds $1.00) → FAIL
header.total_amount = 1005.0
lines sum = 1000.0
```

### E2-F2: Tax Total Consistency
```python
# Exact match → PASS
header.tax = 100.0
line taxes sum = 100.0

# Small diff → WARN
header.tax = 100.50
line taxes sum = 100.0

# Large diff → FAIL
header.tax = 110.0
line taxes sum = 100.0
```

### E2-F3: Discount Math
```python
# Both discount_amount and discount_rate present
# If inconsistent → WARN (always SOFT)
discount_amount = 100.0
discount_rate = 5.0
# Math doesn't match? → SOFT warning
```

### E2-F4: Credit Memo Signs
```python
# Valid credit memo (all negative)
is_credit_memo = true
header.total = -500.0
lines: [-300.0, -200.0]

# Invalid (positive amounts) → FAIL
is_credit_memo = true
header.total = 500.0  # Should be negative → HARD
```

---

## For Developers

### Where the Rules Live
**File**: `app/agents/validation_domain.py`  
**Function**: `_validate_financial_rules(invoice_doc)`

### Understanding Tolerance-Based Severity
```python
ABSOLUTE_TOLERANCE = 1.00

diff = abs(header_total - line_sum)

if diff <= 1.00:
    severity = "SOFT"   # Warning, but continues
else:
    severity = "HARD"   # Blocking failure
```

### Adding a New Financial Rule
```python
def _validate_financial_rules(invoice_doc):
    # ... existing E2 rules ...
    
    # New rule: YOUR_FINANCIAL_CHECK
    if condition:
        issues.append({
            "code": "YOUR_CODE",
            "category": "FINANCIAL",
            "severity": "SOFT" or "HARD",
            "field": "header.your_field",
            "message": "Clear description",
            "metadata": {...}
        })
    
    return issues
```

---

## Issue Codes

| Code | Severity | Tolerance | Field |
|------|----------|-----------|-------|
| `TOTAL_LINE_MISMATCH` | SOFT/HARD | $1.00 | `header.total_amount` |
| `TAX_TOTAL_MISMATCH` | SOFT/HARD | $1.00 | `header.tax_amount` |
| `DISCOUNT_MATH_MISMATCH` | SOFT | N/A | `header.discount` |
| `INVALID_CREDIT_MEMO_SIGN` | HARD | $0.00 | `header.total_amount` |

---

## Status Outcomes

```
ValidationResult.status determination (unchanged):

if any issue with severity == "HARD":
    status = "FAIL"
elif any issue with severity == "SOFT":
    status = "WARN"
else:
    status = "PASS"
```

### Examples
- `TOTAL_LINE_MISMATCH` (SOFT) → Status = WARN → Continue to MatchingAgent
- `TOTAL_LINE_MISMATCH` (HARD) → Status = FAIL → EXCEPTION (stop)
- `INVALID_CREDIT_MEMO_SIGN` (HARD) → Status = FAIL → EXCEPTION (stop)

---

## Orchestrator Integration

```
ValidationDomain runs E2 checks:
  ├─ HARD failures → Set status = FAIL
  └─ SOFT failures → Set status = WARN (if no HARD)
  
Orchestrator branches:
  ├─ FAIL → EXCEPTION (stop)
  └─ WARN → VALIDATED (continue with warnings)
```

---

## Running Tests

```bash
# Test E2 rules specifically
python test_step_e2_financial_rules.py

# Verify backward compatibility
python test_orchestrator_branching.py    # Step D
python test_step_e1_structural_rules.py  # Step E1
```

---

## MongoDB Example: SOFT Issue (WARN)

```json
{
  "_id": "invoice_123",
  "validation": {
    "status": "WARN",
    "issues": [
      {
        "code": "TOTAL_LINE_MISMATCH",
        "category": "FINANCIAL",
        "severity": "SOFT",
        "field": "header.total_amount",
        "message": "Invoice total slightly differs from sum of line amounts",
        "metadata": {
          "header_total": 1000.50,
          "line_sum": 1000.0,
          "diff_abs": 0.5,
          "tolerance": 1.0
        }
      }
    ],
    "summary": {"hard_failures": 0, "soft_warnings": 1},
    "validated_at": "2024-01-01T12:00:00Z"
  }
}
```

---

## MongoDB Example: HARD Issue (FAIL)

```json
{
  "_id": "invoice_123",
  "validation": {
    "status": "FAIL",
    "issues": [
      {
        "code": "TOTAL_LINE_MISMATCH",
        "category": "FINANCIAL",
        "severity": "HARD",
        "field": "header.total_amount",
        "message": "Invoice total does not match sum of line amounts",
        "metadata": {
          "header_total": 1005.0,
          "line_sum": 1000.0,
          "diff_abs": 5.0,
          "tolerance": 1.00
        }
      }
    ],
    "summary": {"hard_failures": 1, "soft_warnings": 0},
    "validated_at": "2024-01-01T12:00:00Z"
  }
}
```

---

## Key Points

✓ **Fixed Tolerance**: $1.00 non-configurable for E2-F1 and E2-F2  
✓ **First WARN Rules**: E2-F3 and soft variants of E2-F1/F2 introduce WARN  
✓ **Per-Issue Evaluation**: Each rule evaluated independently  
✓ **Metadata Rich**: All issues include detailed debugging info  
✓ **Backward Compatible**: All existing tests still pass  

---

## What's NOT Included

✗ Configuration or UI toggles for tolerance  
✗ Configurable severity levels  
✗ Approval workflow changes  
✗ New invoice states  

---

## Tolerance Values (Hard-Coded)

```python
# E2-F1 and E2-F2
ABSOLUTE_TOLERANCE = 1.00  # Non-configurable

# Severity mapping
if diff <= 1.00:
    severity = "SOFT"   # WARN status
else:
    severity = "HARD"   # FAIL status
```

---

## Common Questions

**Q: Why $1.00 tolerance?**  
A: Accounts for rounding differences across systems, typical for currency conversions.

**Q: When does E2-F3 trigger?**  
A: When both discount_amount and discount_rate are present and don't match mathematically.

**Q: Is E2-F3 always WARN?**  
A: Yes - discount mismatches are informational (SOFT) not blocking.

**Q: What about credit memos?**  
A: Mark with `is_credit_memo: true` or `invoice_type: "credit_memo"` and all amounts must be negative.

**Q: Can I configure the tolerance?**  
A: Not in Step E2 - it's $1.00 fixed. Configuration comes in future steps.

---

## Status

✓ **COMPLETE** - All 4 rules implemented  
✓ **TESTED** - 20+ test cases, 100% pass rate  
✓ **BACKWARD COMPATIBLE** - All existing tests pass  
✓ **PRODUCTION READY** - Non-configurable as designed
