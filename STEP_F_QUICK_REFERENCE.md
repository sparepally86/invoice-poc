# Step F Quick Reference - UI Validation Surfacing

## What Changed

### Before
- Invoice Detail showed basic info only
- No visibility into validation results
- Users had to check raw JSON for issues

### After
- **Validation Status Banner** — Prominent green/amber/red status display
- **Validation Tab** — New tab with detailed validation results
- **Issue Grouping** — Issues organized by category
- **Clear Severity** — HARD vs SOFT visually distinct

---

## Three New Components

### 1. ValidationStatusBanner
```jsx
import { ValidationStatusBanner } from '../components/ValidationStatusBanner';

<ValidationStatusBanner validation={invoice.validation} />
```
**Shows**: PASS ✓ / WARN ⚠ / FAIL ✗ with issue count

### 2. ValidationSummary
```jsx
import { ValidationSummary } from '../components/ValidationSummary';

<ValidationSummary validation={invoice.validation} />
```
**Shows**: Collapsible summary of hard failures and soft warnings

### 3. ValidationIssueList
```jsx
import { ValidationIssueList } from '../components/ValidationIssueList';

<ValidationIssueList validation={invoice.validation} />
```
**Shows**: All issues grouped by category with full details

---

## Usage in InvoiceDetail.jsx

```jsx
// 1. Import
import { ValidationStatusBanner } from '../components/ValidationStatusBanner';
import { ValidationSummary } from '../components/ValidationSummary';
import { ValidationIssueList } from '../components/ValidationIssueList';

// 2. Use in render
<ValidationStatusBanner validation={invoice.validation} />

// 3. In Validation tab
<ValidationSummary validation={invoice.validation} />
<ValidationIssueList validation={invoice.validation} />
```

---

## Expected Data Structure

```javascript
invoice.validation = {
  status: "FAIL" | "WARN" | "PASS",
  summary: {
    hard_failures: 2,
    soft_warnings: 1
  },
  issues: [
    {
      code: "EMPTY_DESCRIPTION",
      category: "STRUCTURAL",
      severity: "HARD",
      field: "lines[0].description",
      message: "Line description cannot be empty",
      metadata: { /* optional */ }
    },
    // ... more issues
  ],
  validated_at: "2024-12-30T..."
}
```

---

## User Flow

### Step 1: View Invoices List
```
Navigate to /invoices
See invoices with statuses and amounts
```

### Step 2: Click Invoice
```
Click any invoice number
See Invoice Detail page with:
  ✓ Green/Amber/Red validation banner
  ✓ Basic invoice fields
  ✓ Line items tab
  ✓ [NEW] Validation tab
  ✓ Workflow tab
```

### Step 3: Click Validation Tab
```
See:
  - Summary: X hard failures, Y soft warnings
  - Issues grouped by category
  - Each issue shows code, message, field, severity
```

### Step 4: Review Issues
```
- STRUCTURAL (blue) — Schema/format issues
- FINANCIAL (purple) — Amount/calc issues
- POLICY (orange) — Business rule issues
- DUPLICATE (pink) — Risk issues
```

---

## Status Colors

| Status | Color | Badge | Icon |
|--------|-------|-------|------|
| PASS | Green | #10b981 | ✓ |
| WARN | Amber | #f59e0b | ⚠ |
| FAIL | Red | #ef4444 | ✗ |
| Pending | Gray | #6b7280 | ? |

---

## Category Colors

| Category | Color | Badge |
|----------|-------|-------|
| STRUCTURAL | Blue | #3b82f6 |
| FINANCIAL | Purple | #a855f7 |
| POLICY | Orange | #f97316 |
| DUPLICATE | Pink | #ec4899 |

---

## Severity Indicators

### HARD (Red)
- Must be resolved
- Prevents posting
- Examples: Missing fields, Invalid format

### SOFT (Amber)
- Should be reviewed
- Warning only
- Examples: Minor amount mismatch, Soft policy warning

---

## Component Props

### ValidationStatusBanner
```javascript
{
  validation: {
    status: "FAIL" | "WARN" | "PASS",
    issues: [...],
    summary: {...}
  }
}
```

### ValidationSummary
```javascript
{
  validation: {
    status: "WARN" | "FAIL",
    issues: [...]
  }
}
```

### ValidationIssueList
```javascript
{
  validation: {
    issues: [
      { code, category, severity, field, message, metadata }
    ]
  }
}
```

---

## Error Handling

All components handle null/undefined gracefully:

```javascript
// These are safe
<ValidationStatusBanner validation={null} />
<ValidationStatusBanner validation={undefined} />
<ValidationStatusBanner validation={invoice.validation} />
```

---

## Integration with E8

When you generate an invoice with negative scenarios and submit:

1. **Generate** with scenarios (e.g., Empty Description + Total Mismatch)
2. **Submit** invoice
3. **Backend** validates and emits validation result
4. **UI** automatically shows:
   - Red banner (FAIL status)
   - 2 categories with issues
   - STRUCTURAL and FINANCIAL issues listed

---

## Testing an Invoice

### For PASS Status
Generate invoice with 0 scenarios → Submit → See green banner

### For WARN Status
Generate with SOFT warnings → Submit → See amber banner with issues

### For FAIL Status
Generate with HARD failures → Submit → See red banner with issues

---

## Features at a Glance

✅ Validation status banner (PASS/WARN/FAIL)
✅ Prominent color coding
✅ Issue count display
✅ Collapsible summary section
✅ Category grouping (STRUCTURAL/FINANCIAL/POLICY/DUPLICATE)
✅ Severity indicators (HARD/SOFT)
✅ Field name display
✅ Issue metadata display
✅ Empty state handling
✅ Responsive design
✅ No console errors
✅ Zero performance impact

---

## File Locations

```
frontend/src/
├── components/
│   ├── ValidationStatusBanner.jsx    (61 lines)
│   ├── ValidationSummary.jsx         (81 lines)
│   └── ValidationIssueList.jsx       (181 lines)
└── pages/
    └── InvoiceDetail.jsx             (Modified)
```

---

## Status

✅ **Step F: Complete and Ready for Testing**

All validation results from E1-E8 now surface clearly in the UI!

