# Step E7: Admin UI for Validation Configuration — Specification Prompt

**Objective**: Build an enterprise-grade Admin UI for managing validation rule configurations within the Settings section of the Invoice POC application.

---

## User Story

**As an** AP Operations Manager  
**I want to** configure validation rule thresholds and parameters directly from the UI  
**So that** I can adjust business rules in real-time without code deployment or API calls

---

## Feature Overview

### Location
- **Sidebar**: Add "Validation Rules" under Settings section (alongside Business Rules, Global Settings, etc.)
- **Path**: `/settings/validation-rules`
- **Icon**: Sliders or Wrench icon

### High-Level Capabilities

1. **View Current Configuration**
   - List all 14 validation rules (E1-E4)
   - Show current parameters by organization and region
   - Display effective dates and last modified information
   - Show rule enablement status

2. **Edit Configuration**
   - Update parameters for any rule
   - Set organization-specific overrides
   - Configure region-specific thresholds
   - Set effective date ranges (for time-bound changes like year-end)

3. **Manage Rules**
   - Enable/disable rules per organization
   - View default parameters
   - Compare configurations (ORG-A vs ORG-B, US vs EU)
   - Preview changes before saving

4. **Audit & Compliance**
   - View change history (who, what, when, why)
   - Filter history by date range and user
   - Revert to previous configuration (optional)
   - Export change logs

5. **Multi-Tenant & Multi-Region Management**
   - Organization selector (dropdown)
   - Region selector (US, EU, APAC, ALL)
   - Show resolution order (Specific > Global > Default)
   - Cascade settings from ALL region to specific regions

---

## UI Architecture

### Main Page Layout (Reference: Settings Sample)

```
┌─────────────────────────────────────────────────────────┐
│ Settings                                                │
│ Configure and manage your Alevate AP platform           │
│                                                          │
│ [Search settings...]                                    │
└─────────────────────────────────────────────────────────┘

┌──────────────────────────┬──────────────────────────────┐
│                          │                              │
│  Validation Rules        │  Self-Service Setup          │
│  ─────────────────       │  Business Rules              │
│  Manage financial,       │  Global Settings             │
│  policy, and duplicate   │  Field Settings              │
│  detection thresholds    │  ERP Integration             │
│                          │  Entity Management           │
│  [View Rules]            │                              │
│                          │                              │
└──────────────────────────┴──────────────────────────────┘
```

### Validation Rules Detail Page

**Header Section**:
```
Validation Rules
Manage financial, policy, and duplicate detection thresholds

[Organization: ORG-001 ▼]  [Region: US ▼]  [Sync All Regions] [Import/Export]
```

**Main Content Areas**:

1. **Rules Grid** (Primary)
   - Columns: Rule ID | Rule Name | Category | Current Value | Status | Actions
   - Sortable by category, rule ID, or modification date
   - Quick-view badges for HARD/SOFT severity
   - Enable/Disable toggle per rule
   - Edit/View buttons per rule

2. **Rule Editor Modal** (On Rule Click)
   - Rule name and description
   - Current parameters with input fields
   - Parameter validation and constraints (shown inline)
   - Effective date range selector
   - Change reason/notes field (required)
   - Tabs: Current Value | History | Default
   - [Preview] [Cancel] [Save Changes]

3. **Change History Panel** (Sidebar/Tab)
   - Timeline of recent changes
   - Filter by date range, rule ID, user
   - Show: timestamp, user, field, old value → new value, reason
   - [Revert to This Version] option

4. **Multi-Region Controls** (Right Sidebar)
   - Show resolution order: Specific → ALL → Hardcoded
   - "Cascade to All Regions" option
   - Region comparison view

---

## Rules Configuration Details

### E1: Structural Rules (No Parameters)
- **E1-S1**: Invoice Number Required → Status only (enabled/disabled)
- **E1-S2**: Required Fields Present → Status only
- **E1-S3**: Line Item Consistency → Status only
- **E1-S4**: Numeric Fields Valid → Status only

**UI**: Simple enable/disable toggles, no parameter editing

### E2: Financial Rules (Configurable)

**E2-F1: Amount Tolerance**
- Parameter 1: `tolerance_amount_cents` (integer, 0-10000)
  - Label: "Absolute Tolerance (cents)"
  - Placeholder: "100"
  - Help: "Minimum: 1 cent, Maximum: $100"
  
- Parameter 2: `tolerance_percentage` (float, 0-100)
  - Label: "Tolerance Percentage (%)"
  - Placeholder: "0.5"
  - Help: "0.0 - 100.0%"
  
- Parameter 3: `warning_threshold_percentage` (float, 0-100)
  - Label: "Warning Threshold (%)"
  - Placeholder: "2.0"
  - Help: "Must be ≥ tolerance_percentage"
  - Validation: "warning_threshold must be > tolerance_percentage"

**E2-F2: Line Item Amount**
- Parameter: `tolerance_percentage` (float)
  - Label: "Tolerance Percentage (%)"

**E2-F3: High Amount Threshold**
- Parameter: `high_amount_threshold` (integer, cents)
  - Label: "High Amount Threshold (cents)"
  - Placeholder: "1000000"
  - Help: "Amounts > this trigger extra scrutiny"

**E2-F4: Multi-Currency Sum** → No parameters (status only)

### E3: Policy Rules (Configurable)

**E3-P1: Currency Validation**
- Parameter: `allowed_currencies` (multi-select list)
  - Label: "Allowed Currency Codes"
  - Type: Searchable multi-select dropdown
  - Options: [USD, EUR, GBP, CHF, CAD, AUD, JPY, INR, CNY, ...]
  - Default: ["USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "INR"]
  - Help: "Add/remove currency codes per region"

**E3-P2: Vendor Approval** → No parameters

**E3-P3: Invoice Date Validation**
- Parameter: `date_validation_window_days` (integer, 1-365)
  - Label: "Validation Window (days)"
  - Placeholder: "180"
  - Help: "Invoices older than this trigger warnings"

**E3-P4: Vendor Country**
- Parameter: `required_countries` (multi-select list)
  - Label: "Allowed Countries"
  - Type: Searchable multi-select dropdown
  - Options: [US, CA, MX, GB, DE, FR, IT, ES, AU, JP, CN, ...]
  - Default: ["US", "EU"]

### E4: Duplicate Rules (Configurable)

**E4-D1: Exact Match** → No parameters

**E4-D2: Time-Window Duplicate**
- Parameter: `time_window_days` (integer, 1-365)
  - Label: "Detection Window (days)"
  - Placeholder: "30"
  - Help: "Check for duplicates within N days"

**E4-D3: Similar Amount Heuristic**
- Parameter 1: `similar_amount_tolerance_pct` (float, 0-100)
  - Label: "Amount Tolerance (%)"
  - Placeholder: "2.0"
  
- Parameter 2: `time_window_days` (integer, 1-365)
  - Label: "Time Window (days)"
  - Placeholder: "60"

---

## Form Validation Rules

**Real-time Validation**:
- Type checking: Reject non-numeric input for integer/float fields
- Range checking: Show error if value outside min/max bounds
- Cross-parameter: "tolerance_percentage must be ≤ warning_threshold_percentage"
- Currency codes: Validate ISO-4217 format (show warning for unknown codes)
- Required fields: Mark with * and show error if empty on save

**Display**:
- Inline error messages (red text below field)
- Success badges (green checkmark after valid entry)
- Help text on field hover (info icon)
- Visual constraint display (min/max bounds shown)

---

## Key User Workflows

### Workflow 1: Increase Tolerance for Year-End

1. Open Settings → Validation Rules
2. Organization: ORG-001, Region: US
3. Click on E2-F1 (Amount Tolerance)
4. Update: tolerance_amount_cents = 500 (was 100)
5. Set Effective Date: Dec 20, 2025 → Jan 10, 2026
6. Reason: "Year-end reconciliation"
7. [Preview] → shows before/after
8. [Save Changes]
9. ✅ Confirmation toast: "E2-F1 updated successfully"
10. Change appears in history immediately

### Workflow 2: Add New Currency for Regional Expansion

1. Settings → Validation Rules
2. Organization: ORG-002, Region: APAC
3. Click on E3-P1 (Currency Validation)
4. Add "CNY" to allowed_currencies (currently: USD, EUR, GBP, CHF, CAD, AUD, JPY, INR)
5. Reason: "China expansion Q1 2026"
6. [Save Changes]
7. ✅ Confirmation: "E3-P1 updated. CNY now accepted in APAC region"

### Workflow 3: Compare Two Organizations

1. Settings → Validation Rules
2. Organization: ORG-001, Region: US
3. [Compare Organizations] button
4. Select: ORG-002 for comparison
5. Side-by-side view showing configuration differences
6. Highlights where ORG-001 ≠ ORG-002
7. [Copy from ORG-001 to ORG-002] (copy entire config)

### Workflow 4: View and Audit Changes

1. Settings → Validation Rules
2. Click [View History] tab
3. Filter by: Last 30 days, Rule: E2-F1, User: admin@company.com
4. See chronological list:
   - 2025-12-30 10:00 | admin@company.com | E2-F1 | tolerance_amount_cents | 100→500 | "Year-end"
   - 2025-12-15 14:30 | ops@company.com | E2-F1 | tolerance_percentage | 0.5%→0.7% | "Q4 adjustment"
5. [Revert to 2025-12-15 version] option

---

## Components & Interaction Patterns

### Component 1: Rule Card (Grid View)

```
┌─────────────────────────────────────────────────────────┐
│ E2-F1                Amount Tolerance           [●●●]   │
│ FINANCIAL | SOFT     $1.00 ± 0.5%                       │
│ Set amount tolerance thresholds for invoices            │
│                                                          │
│ Enabled ✓  |  Last Modified: 2025-12-30 by admin       │
│                                                          │
│ [View Details]  [Edit]  [View History]  [Disable]      │
└─────────────────────────────────────────────────────────┘
```

### Component 2: Parameter Editor

```
Tolerance Amount
Absolute tolerance in cents
[____100____] ⓘ Help text here
Constraints: min=1, max=10000
✓ Valid

Warning Threshold (%)
Must be greater than tolerance percentage
[____2.0____] %
Constraints: min=0, max=100
✗ Error: Must be > 0.5%
```

### Component 3: Change History Timeline

```
═══ CHANGE HISTORY ════════════════════════════════
  
  2025-12-30 10:00  admin@company.com
  ↓  
  E2-F1: tolerance_amount_cents
  100 → 500
  "Year-end reconciliation"
  [Revert]
  
  ─────────────────────────
  
  2025-12-15 14:30  ops@company.com
  ↓
  E2-F1: tolerance_percentage
  0.5 → 0.7%
  "Q4 adjustment"
  [Revert]
```

---

## API Integration

### Backend Endpoints Used

```javascript
// Get current configuration
GET /api/v1/admin/validation-config?org_id=ORG-001&region=US

// Get specific rule
GET /api/v1/admin/validation-config/E2-F1?org_id=ORG-001&region=US

// Update rule
PUT /api/v1/admin/validation-config/E2-F1
{
  "org_id": "ORG-001",
  "region": "US",
  "parameters": {
    "tolerance_amount_cents": 500,
    "tolerance_percentage": 2.0
  },
  "effective_from": "2025-12-20T00:00:00Z",
  "effective_to": "2026-01-10T23:59:59Z",
  "reason": "Year-end reconciliation"
}

// Get defaults
GET /api/v1/admin/validation-config/defaults?rule_id=E2-F1

// Get history
GET /api/v1/admin/validation-config/history?org_id=ORG-001&days=30&rule_id=E2-F1

// Validate parameters
POST /api/v1/admin/validation-config/validate
{
  "rule_id": "E2-F1",
  "parameters": {...}
}

// Disable rule
PUT /api/v1/admin/validation-config/E2-F1/disable
{
  "org_id": "ORG-001",
  "reason": "Database migration"
}
```

---

## Technical Requirements

### Frontend Stack
- **Framework**: React with Vite (existing)
- **Styling**: Tailwind CSS (existing)
- **Icons**: lucide-react (existing)
- **Form Handling**: React Hook Form + Zod validation
- **State Management**: React Context or Zustand
- **HTTP Client**: axios or fetch

### State Management
```javascript
{
  selectedOrg: "ORG-001",
  selectedRegion: "US",
  rules: [
    { id: "E2-F1", name: "Amount Tolerance", category: "FINANCIAL", ...}
  ],
  currentRule: null,  // For modal editing
  history: [],
  loading: false,
  error: null
}
```

### Components to Create
- `ValidationRulesPage.jsx` — Main container
- `RulesGrid.jsx` — List of all rules
- `RuleCard.jsx` — Individual rule card
- `RuleEditor.jsx` — Modal for editing parameters
- `ParameterInput.jsx` — Reusable parameter input field
- `ChangeHistoryPanel.jsx` — Audit trail view
- `ComparisonView.jsx` — Multi-org comparison
- `SelectiveSync.jsx` — Region cascade controls

---

## Design Specifications

### Color Scheme
- **Rules Grid**: Light card backgrounds, subtle shadows
- **Edit Mode**: Blue highlight for active fields
- **Validation**: Green for valid, Red for invalid
- **Categories**: 
  - E1 Structural: Blue badge
  - E2 Financial: Purple badge
  - E3 Policy: Orange badge
  - E4 Duplicate: Pink badge

### Responsive Design
- **Desktop**: Full grid layout with side-by-side comparison
- **Tablet**: Stacked layout, collapse history panel
- **Mobile**: Modal for rule editing, list view only

### Accessibility
- ARIA labels on all form inputs
- Keyboard navigation for rule selection
- Tab order for form fields
- Screen reader support for validation errors

---

## Success Criteria

✅ **Phase 1: Core UI**
- [ ] Navigation link added to Settings
- [ ] Rules grid displaying all 14 rules
- [ ] Rule details modal working
- [ ] Parameter editing functional

✅ **Phase 2: Validation & Form Handling**
- [ ] Real-time parameter validation
- [ ] Cross-parameter validation (tolerance < warning)
- [ ] Error messages displaying correctly
- [ ] Form submission to backend API

✅ **Phase 3: Multi-Tenant Management**
- [ ] Organization selector working
- [ ] Region selector working
- [ ] Configuration resolution order showing
- [ ] Region cascade controls working

✅ **Phase 4: Audit & History**
- [ ] Change history panel displaying
- [ ] History filtering by date/rule/user
- [ ] Revert functionality working

✅ **Phase 5: Advanced Features**
- [ ] Comparison view (org vs org)
- [ ] Import/Export configurations
- [ ] Bulk rule updates
- [ ] Scheduled configuration changes

---

## Deliverables

**Frontend Files**:
- `frontend/src/pages/Settings/ValidationRules.jsx` — Main page
- `frontend/src/pages/Settings/ValidationRulesDetails.jsx` — Detail view
- `frontend/src/components/Settings/RulesGrid.jsx` — Grid display
- `frontend/src/components/Settings/RuleEditor.jsx` — Edit modal
- `frontend/src/components/Settings/ChangeHistory.jsx` — Audit trail
- `frontend/src/lib/api/validation-config.js` — API client

**Updated Files**:
- `frontend/src/components/Sidebar.jsx` — Add Validation Rules link
- `frontend/src/App.jsx` — Add new routes

**Test Files**:
- `frontend/src/components/Settings/__tests__/RuleEditor.test.jsx`
- `frontend/src/lib/api/__tests__/validation-config.test.js`

---

## Implementation Timeline

**Phase 1**: 4 hours (Core UI, grid, modal)  
**Phase 2**: 3 hours (Validation, API integration)  
**Phase 3**: 3 hours (Multi-tenant, region controls)  
**Phase 4**: 2 hours (Audit trail, history)  
**Phase 5**: 3 hours (Advanced features, testing)

**Total**: ~15 hours

---

## Notes

- Defer "Revert to Version" until E7.2 (requires backend versioning)
- Authorization: Use existing JWT token from header (already in place)
- Caching: Validation rules cache expires in 5 minutes (backend managed)
- No real-time updates needed (changes effective after refresh)
- Mobile first is secondary priority (desktop focus for initial release)

