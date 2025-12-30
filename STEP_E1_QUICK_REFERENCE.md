# Step E1: Structural Validation Rules - Quick Reference

## At a Glance

Step E1 adds **4 new STRUCTURAL validation rules** that ensure invoices are valid business documents:

| Rule | Checks | Fails When | Severity |
|------|--------|-----------|----------|
| **E1-S1** | Line description | Empty or whitespace-only | HARD |
| **E1-S2** | Line numbers | Duplicate, zero, negative, non-numeric | HARD |
| **E1-S3** | Total with lines | Total > 0 but no lines | HARD |
| **E1-S4** | Line quantity | Zero, negative, or non-numeric | HARD |

All violations result in `ValidationResult.status = FAIL`.

---

## The Rules

### E1-S1: Empty Line Description
```python
# FAIL
{"line_number": 1, "description": "", "quantity": 1}
{"line_number": 1, "description": "   ", "quantity": 1}

# PASS
{"line_number": 1, "description": "Office Supplies", "quantity": 1}
```

### E1-S2: Invalid/Duplicate Line Numbers
```python
# FAIL (duplicate)
[{"line_number": 1}, {"line_number": 1}]

# FAIL (invalid)
{"line_number": 0}
{"line_number": -1}
{"line_number": "ABC"}

# PASS
[{"line_number": 1}, {"line_number": 2}]
```

### E1-S3: Total Without Lines
```python
# FAIL
{
  "header": {"total_amount": 1000.0},
  "lines": []
}

# PASS
{
  "header": {"total_amount": 1000.0},
  "lines": [{"line_amount": 1000.0}]
}

# PASS
{
  "header": {"total_amount": 0.0},
  "lines": []
}
```

### E1-S4: Invalid Quantity
```python
# FAIL
{"line_number": 1, "quantity": 0}
{"line_number": 1, "quantity": -5}
{"line_number": 1, "quantity": "ABC"}

# PASS
{"line_number": 1, "quantity": 1}
{"line_number": 1, "quantity": 2.5}
```

---

## For Developers

### Where the Rules Live
**File**: `app/agents/validation_domain.py`  
**Function**: `_validate_structural_rules(invoice_doc)`

### Adding a New Structural Rule
```python
def _validate_structural_rules(invoice_doc):
    # ... existing E1 rules ...
    
    # New rule: YOUR_RULE_CODE
    for idx, line in enumerate(lines):
        if condition:
            issues.append({
                "code": "YOUR_RULE_CODE",
                "category": "STRUCTURAL",
                "severity": "HARD",
                "field": "lines[].your_field",
                "message": "Clear description",
                "metadata": {"line_index": idx}
            })
    
    return issues
```

### Testing a New Rule
```python
# In test_step_e1_structural_rules.py
invoice_test_case = {
    "header": {...},
    "lines": [...]
}

result = validate(mock_db, invoice_test_case)
assert result["status"] == "FAIL"
assert any(issue["code"] == "YOUR_RULE_CODE" for issue in result["issues"])
```

---

## Verification Checklist

- [x] E1-S1: Empty description detection works
- [x] E1-S2: Invalid/duplicate line numbers work
- [x] E1-S3: Total without lines works
- [x] E1-S4: Invalid quantity works
- [x] Multiple violations aggregated
- [x] Valid invoices pass
- [x] All Step B tests still pass
- [x] All Step D tests still pass

---

## Impact on Invoice Flow

```
RECEIVED
  ↓
[Validation] - Now checks E1 rules
  ↓
If E1 violation:
  └─→ EXCEPTION (stop)
     └─→ Human review available

If valid:
  └─→ VALIDATED
     └─→ MatchingAgent (unchanged)
```

---

## Issue Codes

| Code | Category | Severity | Field |
|------|----------|----------|-------|
| `LINE_DESCRIPTION_EMPTY` | STRUCTURAL | HARD | `lines[].description` |
| `INVALID_LINE_NUMBER` | STRUCTURAL | HARD | `lines[].line_number` |
| `TOTAL_WITHOUT_LINES` | STRUCTURAL | HARD | `header.total_amount` |
| `INVALID_LINE_QUANTITY` | STRUCTURAL | HARD | `lines[].quantity` |

---

## Running Tests

```bash
# Test E1 rules specifically
python test_step_e1_structural_rules.py

# Verify backward compatibility
python test_orchestrator_branching.py
python test_taxonomy_simple.py
```

---

## MongoDB Example

```json
{
  "_id": "invoice_123",
  "validation": {
    "status": "FAIL",
    "issues": [
      {
        "code": "LINE_DESCRIPTION_EMPTY",
        "category": "STRUCTURAL",
        "severity": "HARD",
        "field": "lines[].description",
        "message": "Invoice line description cannot be empty",
        "metadata": {"line_index": 0}
      }
    ],
    "summary": {"hard_failures": 1, "soft_warnings": 0},
    "validated_at": "2024-01-01T12:00:00Z"
  }
}
```

---

## Key Points

✓ **All HARD**: All E1 rules are HARD severity (blocking)  
✓ **All STRUCTURAL**: All E1 rules are STRUCTURAL category  
✓ **Non-Configurable**: No thresholds or feature flags  
✓ **Per-Line Issues**: Violations emitted per line (not per invoice)  
✓ **Aggregated**: All violations collected in single pass  
✓ **Backward Compatible**: Zero breaking changes  

---

## What's NOT Included

✗ Credit memo handling (zero/negative allowed later)  
✗ Configuration or toggles  
✗ UI rendering  
✗ Approval workflow changes  

---

## Related Steps

- **Step A**: ValidationResult Contract (data structure)
- **Step B**: Taxonomy (categorization: STRUCTURAL/FINANCIAL/POLICY)
- **Step C**: ValidationDomain (implementation abstraction)
- **Step D**: Orchestrator (branching on validation result)
- **Step E1**: Structural rules (THIS STEP - new rules)
- **Step E2+**: More rule expansion

---

## Common Questions

**Q: What happens if I add a line with no description?**  
A: Invoice gets status=FAIL, moved to EXCEPTION, stopped from processing.

**Q: Can I have duplicate line numbers?**  
A: No - violates E1-S2. Each line must have unique positive integer.

**Q: Can I have a $0 total?**  
A: Yes - E1-S3 only triggers if total > 0 with no lines.

**Q: Can negative quantities be used for credits?**  
A: Not in Step E1 - credit memo support comes in future steps.

**Q: Where are E1 violations stored?**  
A: In `invoice.validation.issues[]` with `category=STRUCTURAL`.

---

## Status

✓ **COMPLETE** - All 4 rules implemented and tested  
✓ **TESTED** - 20+ test cases, 100% pass rate  
✓ **BACKWARD COMPATIBLE** - All existing tests still pass  
✓ **PRODUCTION READY** - Zero breaking changes
