# ValidationResult Contract — Quick Reference

## ValidationResult Structure

```json
{
  "status": "PASS" | "WARN" | "FAIL",
  "issues": [
    {
      "code": "MISSING_FIELD",
      "category": "STRUCTURAL" | "FINANCIAL" | "POLICY" | "DUPLICATE",
      "severity": "HARD" | "SOFT",
      "field": "header.invoice_number",
      "message": "Human readable explanation",
      "metadata": { "optional": "details" }
    }
  ],
  "summary": {
    "hard_failures": 1,
    "soft_warnings": 0
  },
  "validated_at": "2025-12-30T11:00:00Z"
}
```

## Status Rules

| Issues | Status |
|--------|--------|
| None | `PASS` |
| Only SOFT | `WARN` |
| Any HARD | `FAIL` |

## Issue Categories

- **STRUCTURAL**: Schema/format violations (MISSING_FIELD)
- **FINANCIAL**: Amount/currency issues (AMOUNT_MISMATCH)
- **POLICY**: Business rules (VENDOR_NOT_FOUND)
- **DUPLICATE**: Duplicates (DUPLICATE_INVOICE - future)

## Severity Levels

- **HARD**: Critical, blocks processing
- **SOFT**: Warning, should be reviewed

## MongoDB Location

```
db.invoices
  └─ validation: { ... }
```

## Query Examples

```javascript
// Find failed invoices
db.invoices.find({ "validation.status": "FAIL" })

// Find invoices with hard failures
db.invoices.find({ "validation.summary.hard_failures": { $gt: 0 } })

// Find financial issues
db.invoices.find({ "validation.issues.category": "FINANCIAL" })

// Get validation count
db.invoices.countDocuments({ "validation": { $exists: true } })
```

## Code Integration

### In ValidationAgent
```python
from app.agents.validation import _build_validation_result

# Build result
issues = [...]  # list of structured issues
validation_result = _build_validation_result(issues, datetime_iso_string)

# Returns:
# {
#   "status": "PASS" | "WARN" | "FAIL",
#   "issues": [...],
#   "summary": {...},
#   "validated_at": "..."
# }
```

### In Orchestrator
```python
# Extract from agent output
validation_result = validation_out.get("validation")

# Persist to invoice
if validation_result:
    db.invoices.update_one(
        {"_id": invoice_id},
        {"$set": {"validation": validation_result}}
    )
```

## Testing

```bash
# Unit tests
python test_validation_contract.py

# Demonstration
python demo_validation_result.py

# Integration (requires API server)
python test_validation_result_integration.py
```

## Files Modified

1. `app/agents/validation.py` (+85 lines)
2. `app/orchestrator.py` (+5 lines)

## Key Files

- `IMPLEMENTATION_SUMMARY.md` - Full technical documentation
- `VALIDATION_RESULT_GUIDE.md` - User guide
- `IMPLEMENTATION_CHECKLIST.md` - Verification checklist
- `IMPLEMENTATION_COMPLETE.md` - Executive summary

## Status: ✅ COMPLETE

All tests passing • Backward compatible • Ready for production
