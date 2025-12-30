# Step E5: Configuration System — Specification Prompt

**Status**: Ready for Review  
**Target Implementation**: Upon approval  
**Scope**: Extract hard-coded validation parameters into dynamic configuration system  

---

## Overview

Step E5 introduces a **Configuration System** that makes validation rules dynamically configurable without code changes. Currently, all validation thresholds and windows are hard-coded in `app/agents/validation_domain.py`. Step E5 extracts these into MongoDB-backed configuration that can be managed via admin API and UI.

### Problem Solved

**Before E5**:
- Thresholds hard-coded (2% tolerance, 30-day windows, $1M high-amount threshold)
- Changing a rule requires code modification and redeployment
- No audit trail for configuration changes
- No multi-tenant or multi-region configuration support

**After E5**:
- Thresholds managed in database (no code changes needed)
- Admin API to create/update/delete validation rules
- Configuration caching for performance
- Complete audit trail of who changed what and when
- Per-organization and per-region configuration support
- Enable/disable rules by organization
- Different thresholds for different regions

---

## Architecture

### 1. MongoDB Schema: `validation_config` Collection

**Purpose**: Central repository for all validation configuration

**Document Structure**:

```json
{
  "_id": "ObjectId",
  "organization_id": "ORG-001",
  "region": "US",  // "US", "EU", "APAC", "ALL" (ALL = global default)
  "rule_id": "E2-F1",  // E1-S1, E2-F1, E3-P1, E4-D1, etc.
  "rule_name": "Amount Tolerance",
  "rule_category": "FINANCIAL",  // STRUCTURAL, FINANCIAL, POLICY, DUPLICATE
  "enabled": true,
  "severity": "SOFT",  // HARD or SOFT (auto-derived from rules logic in E5)
  "parameters": {
    // Rule-specific parameters (extracted from hard-coded values in E1-E4)
    "tolerance_amount_cents": 100,  // $1.00 in cents
    "tolerance_percentage": 0.5,    // 0.5%
    "warning_threshold_percentage": 2.0,  // 2.0%
    "high_amount_threshold": 1000000,  // $1M
    "allowed_currencies": ["USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "INR"],
    "date_validation_window_days": 180,
    "required_countries": ["US", "EU"],
    "time_window_days": 30,  // For E4-D2
    "similar_amount_tolerance_pct": 2.0,  // For E4-D3
    "custom_field": "any_value"  // Extensible for future rules
  },
  "created_at": "2025-12-30T10:00:00Z",
  "created_by": "admin@company.com",
  "updated_at": "2025-12-30T10:00:00Z",
  "updated_by": "admin@company.com",
  "change_history": [
    {
      "timestamp": "2025-12-30T10:00:00Z",
      "changed_by": "admin@company.com",
      "field_changed": "tolerance_amount_cents",
      "old_value": 50,
      "new_value": 100,
      "reason": "Increased tolerance for year-end reconciliation"
    }
  ],
  "tags": ["year-end", "temporary"],
  "effective_from": "2025-12-30T00:00:00Z",
  "effective_to": "2025-12-31T23:59:59Z",  // null for no expiration
  "notes": "Temporary adjustment for holiday invoicing"
}
```

**Indexes**:
- `{organization_id: 1, region: 1, rule_id: 1}` (unique)
- `{organization_id: 1, enabled: 1}` (for retrieving active config)
- `{rule_category: 1, organization_id: 1}` (for category queries)
- `{updated_at: -1}` (for audit trail queries)

---

### 2. Configuration Service

**File**: `app/services/config_service.py` (NEW)

**Purpose**: Load, cache, and manage configuration

**Key Functions**:

```python
class ConfigurationService:
    """
    Manages validation rule configuration with caching and fallback to defaults.
    """
    
    async def get_rule_config(
        org_id: str,
        rule_id: str,
        region: str = "US"
    ) -> dict:
        """
        Get configuration for specific rule.
        
        Resolution order:
        1. Organization + Region specific
        2. Organization + "ALL" region (global)
        3. Hardcoded defaults (fallback)
        
        Returns cached value if available (5-minute TTL).
        """
        
    async def get_all_active_rules(
        org_id: str,
        region: str = "US"
    ) -> List[dict]:
        """
        Get all enabled validation rules for organization/region.
        Returns cached list (5-minute TTL).
        """
        
    async def reload_config(
        org_id: str,
        region: str = None
    ) -> None:
        """
        Invalidate cache for specific org/region.
        Called after config updates.
        """
        
    async def validate_config_params(
        rule_id: str,
        parameters: dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that parameters are valid for rule.
        Returns (is_valid, error_message).
        """
```

**Caching Strategy**:
- Use Redis or in-memory cache with 5-minute TTL
- Cache key: `validation_config:{org_id}:{region}:{rule_id}`
- Invalidate on configuration change
- Fallback to database on cache miss
- Fallback to hardcoded defaults if database has no entry

---

### 3. ValidationDomain Integration

**File**: `app/agents/validation_domain.py` (MODIFIED)

**Changes**:

1. **Add ConfigurationService as dependency**:
```python
async def run_validation(
    db: pymongo.database.Database,
    invoice_doc: dict,
    org_id: str,
    region: str = "US",
    config_service: ConfigurationService = None  # NEW parameter
) -> dict:
    """
    Run all validation rules using configuration service.
    
    If config_service not provided, use hardcoded defaults.
    Maintains backward compatibility with E1-E4 code.
    """
```

2. **Use config in each validation function**:
```python
async def _validate_financial_rules(
    db, invoice_doc, config_service, org_id, region
):
    # Get config
    amount_config = await config_service.get_rule_config(
        org_id, "E2-F1", region
    )
    
    # Use parameters from config (with hardcoded fallback)
    tolerance_cents = amount_config.get('parameters', {}).get(
        'tolerance_amount_cents', 100  # Default fallback
    )
    
    # Rest of logic unchanged
```

3. **Replace all hard-coded values with config lookups**:
   - `_validate_financial_rules()`: tolerance_amount_cents, tolerance_percentage, warning_threshold_percentage
   - `_validate_policy_rules()`: allowed_currencies, date_validation_window_days, high_amount_threshold, required_countries
   - `_validate_duplicate_rules()`: time_window_days (30/60), similar_amount_tolerance_pct

4. **Backward Compatibility**:
   - All existing E1-E4 tests pass without modification
   - If org_id/region not provided, use defaults
   - If config service not provided, use hardcoded values
   - Graceful degradation if config lookup fails

---

### 4. Admin API Endpoints

**File**: `app/api/admin_config.py` (NEW)

**Base Path**: `/api/v1/admin/validation-config`

**Endpoints**:

#### GET all configuration for organization

```
GET /api/v1/admin/validation-config
Query params: org_id, region (optional, default "US")

Response:
{
  "data": [
    {
      "rule_id": "E2-F1",
      "rule_name": "Amount Tolerance",
      "enabled": true,
      "parameters": {...},
      "updated_at": "2025-12-30T10:00:00Z",
      "change_count": 5
    }
  ],
  "total": 15,
  "region": "US",
  "org_id": "ORG-001"
}
```

#### GET specific rule configuration

```
GET /api/v1/admin/validation-config/{rule_id}
Query params: org_id, region (optional)

Response:
{
  "rule_id": "E2-F1",
  "rule_name": "Amount Tolerance",
  "category": "FINANCIAL",
  "enabled": true,
  "parameters": {
    "tolerance_amount_cents": 100,
    "tolerance_percentage": 0.5,
    "warning_threshold_percentage": 2.0
  },
  "created_at": "2025-12-30T10:00:00Z",
  "updated_at": "2025-12-30T10:00:00Z",
  "change_history": [...]
}
```

#### UPDATE rule configuration

```
PUT /api/v1/admin/validation-config/{rule_id}
Body:
{
  "org_id": "ORG-001",
  "region": "US",
  "enabled": true,
  "parameters": {
    "tolerance_amount_cents": 150,
    "tolerance_percentage": 0.75
  },
  "effective_from": "2025-12-30T00:00:00Z",
  "effective_to": "2026-01-31T23:59:59Z",
  "reason": "Year-end tolerance increase"
}

Response:
{
  "success": true,
  "rule_id": "E2-F1",
  "updated_at": "2025-12-30T10:00:00Z"
}
```

#### DISABLE rule

```
PUT /api/v1/admin/validation-config/{rule_id}/disable
Body: { "org_id": "ORG-001", "reason": "Testing" }

Response:
{
  "success": true,
  "rule_id": "E2-F1",
  "enabled": false
}
```

#### GET configuration change history

```
GET /api/v1/admin/validation-config/history
Query params: org_id, rule_id (optional), days=30

Response:
{
  "data": [
    {
      "timestamp": "2025-12-30T10:00:00Z",
      "changed_by": "admin@company.com",
      "rule_id": "E2-F1",
      "field": "tolerance_amount_cents",
      "old_value": 100,
      "new_value": 150,
      "reason": "Year-end adjustment"
    }
  ],
  "total": 42
}
```

#### VALIDATE configuration parameters

```
POST /api/v1/admin/validation-config/validate
Body:
{
  "rule_id": "E2-F1",
  "parameters": {
    "tolerance_amount_cents": 150,
    "tolerance_percentage": 0.75
  }
}

Response:
{
  "valid": true,
  "errors": []
}
```

#### GET default configuration (hardcoded fallback)

```
GET /api/v1/admin/validation-config/defaults
Query params: rule_id (optional)

Response:
{
  "data": [
    {
      "rule_id": "E2-F1",
      "parameters": {
        "tolerance_amount_cents": 100,
        "tolerance_percentage": 0.5,
        "warning_threshold_percentage": 2.0
      }
    }
  ]
}
```

**Authorization**:
- All endpoints require `Authorization: Bearer {admin_token}`
- Permission checks: only admin role can modify config
- Audit log all configuration changes

---

### 5. Configuration Validation

**File**: `app/services/config_validator.py` (NEW)

**Purpose**: Validate configuration parameters for each rule

**Validation Rules**:

```python
VALIDATION_RULES = {
    "E2-F1": {  # Amount Tolerance
        "tolerance_amount_cents": {"type": int, "min": 0, "max": 100000},
        "tolerance_percentage": {"type": float, "min": 0.0, "max": 5.0},
        "warning_threshold_percentage": {"type": float, "min": 0.0, "max": 10.0}
    },
    "E2-F2": {  # Line Total Match
        "tolerance_percentage": {"type": float, "min": 0.0, "max": 5.0}
    },
    "E3-P1": {  # Currency Validation
        "allowed_currencies": {"type": list, "items": str, "min_items": 1, "max_items": 50}
    },
    "E3-P3": {  # Date Validation
        "date_validation_window_days": {"type": int, "min": 1, "max": 365}
    },
    "E4-D2": {  # Time-Window Duplicate
        "time_window_days": {"type": int, "min": 1, "max": 365}
    },
    "E4-D3": {  # Similar Amount Heuristic
        "similar_amount_tolerance_pct": {"type": float, "min": 0.1, "max": 10.0},
        "time_window_days": {"type": int, "min": 1, "max": 365}
    }
}

def validate_parameters(rule_id: str, parameters: dict) -> Tuple[bool, List[str]]:
    """
    Validate parameters against schema.
    Returns (is_valid, error_messages).
    """
```

**Cross-Parameter Validation**:
- `tolerance_percentage` should be <= `warning_threshold_percentage`
- `time_window_days` should be positive
- `allowed_currencies` should be ISO-4217 codes
- `effective_from` should be before `effective_to`

---

## Implementation Details

### Phase 1: Configuration Infrastructure

1. **Create ConfigurationService** (`app/services/config_service.py`)
   - Initialize config cache
   - Implement get_rule_config() with fallback
   - Implement get_all_active_rules()
   - Implement reload_config() for cache invalidation
   - Add caching logic (5-minute TTL)

2. **Create ConfigValidator** (`app/services/config_validator.py`)
   - Define VALIDATION_RULES dictionary
   - Implement validate_parameters()
   - Add cross-parameter validation

3. **Modify ValidationDomain** (`app/agents/validation_domain.py`)
   - Add config_service parameter to run_validation()
   - Update each rule function to use config
   - Replace all hard-coded values with config lookups
   - Add fallback to hardcoded defaults
   - Maintain 100% backward compatibility

### Phase 2: Admin API

1. **Create Admin API** (`app/api/admin_config.py`)
   - Implement all 7 endpoints
   - Add authorization checks
   - Add audit logging for all modifications
   - Add error handling and validation

2. **Create Admin Models** (`app/models/admin_config.py`)
   - ConfigurationUpdate schema
   - ConfigurationResponse schema
   - ChangeHistoryEntry schema
   - ValidationError response

### Phase 3: Database & Migration

1. **Create MongoDB indexes** on validation_config collection
2. **Create seed data** with default configuration for all E1-E4 rules
3. **Create migration helper** to populate defaults from hard-coded values

### Phase 4: Testing

1. **Unit Tests** (`app/tests/test_config_service.py`)
   - Config loading and caching
   - Fallback to defaults
   - Cache invalidation
   - Parameter validation

2. **Integration Tests** (`test_step_e5_config_system.py`)
   - Full workflow: update config → reload → validate with new config
   - Multi-tenant isolation
   - Multi-region configuration
   - Admin API endpoints
   - Backward compatibility (E1-E4 tests unchanged)

3. **Backward Compatibility** (`test_step_e5_backward_compat.py`)
   - All E1-E4 tests pass without modification
   - ValidationDomain works with and without config_service

---

## Hard-Coded Values to Extract

### From E2 (Financial Rules):
```python
# E2-F1: Amount Tolerance
"tolerance_amount_cents": 100  # $1.00
"tolerance_percentage": 0.5  # 0.5%
"warning_threshold_percentage": 2.0  # 2.0%

# E2-F3: High Amount Threshold
"high_amount_threshold": 1000000  # $1M
```

### From E3 (Policy Rules):
```python
# E3-P1: Currency Validation
"allowed_currencies": ["USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "INR"]

# E3-P3: Date Validation
"date_validation_window_days": 180

# E3-P4: Vendor Country Requirement
"required_countries": ["US", "EU"]  # Organization-specific
```

### From E4 (Duplicate Rules):
```python
# E4-D2: Time-Window Duplicate
"time_window_days": 30

# E4-D3: Similar Amount Heuristic
"similar_amount_tolerance_pct": 2.0
"time_window_days": 60
```

---

## Multi-Tenant & Multi-Region Support

### Organization Isolation

```
Config Resolution:
1. ORG-001 + US + E2-F1 → Use org-specific config
2. ORG-001 + EU + E2-F1 → Not found, use ORG-001 + ALL + E2-F1
3. ORG-001 + APAC + E2-F1 → Use default hardcoded
```

### Region Support

**Supported Regions**: US, EU, APAC, ALL (global default)

**Use Cases**:
- US organization stricter currency validation (only USD)
- EU organization requires EUR + local currencies
- Different high-amount thresholds per region
- Organization-specific date validation windows

**Example Config**:
```json
{
  "organization_id": "ORG-001",
  "region": "US",
  "rule_id": "E3-P1",
  "parameters": {
    "allowed_currencies": ["USD"]  // US-specific
  }
}
```

---

## Non-Goals (Step E5 Scope Boundaries)

- ❌ No UI for configuration management (frontend work, future)
- ❌ No real-time configuration updates (requires WebSocket, future)
- ❌ No ML-based parameter suggestions (future)
- ❌ No configuration versioning/rollback (future, but audit trail supports it)
- ❌ No API rate limiting on admin endpoints (future)
- ❌ No encryption of sensitive parameters (future)

---

## Testing Strategy

### Unit Tests (`app/tests/test_config_service.py`)

1. **Configuration Loading**:
   - Get specific rule config (org + region)
   - Get all active rules
   - Fallback to default when missing
   
2. **Caching**:
   - Cache hit returns same object
   - Cache miss queries database
   - Cache invalidation works
   - TTL expiration triggers reload

3. **Parameter Validation**:
   - Valid parameters pass
   - Invalid types rejected
   - Out-of-range values rejected
   - Cross-parameter validation (tolerance_percentage < warning_threshold)

### Integration Tests (`test_step_e5_config_system.py`)

1. **Admin API Workflow**:
   - Create configuration
   - Update configuration
   - Get configuration history
   - Disable rule
   - Validate parameters

2. **Multi-Tenant**:
   - ORG-001 configuration isolated from ORG-002
   - Organization-specific values don't leak
   - Default config available if org has no config

3. **Multi-Region**:
   - US region uses US config
   - EU region uses EU config
   - Fallback to ALL region if specific missing
   - Fallback to hardcoded if ALL missing

4. **Validation Integration**:
   - Submit invoice with org + region
   - Validation uses org-specific config
   - Thresholds apply correctly
   - Results differ based on org config

5. **Backward Compatibility**:
   - All E1-E4 tests pass unchanged
   - ValidationDomain works without config_service
   - Hardcoded defaults work as fallback

---

## Files to Create/Modify

### NEW Files:
1. `app/services/config_service.py` — Configuration loading and caching
2. `app/services/config_validator.py` — Parameter validation
3. `app/api/admin_config.py` — Admin API endpoints
4. `app/models/admin_config.py` — API schemas
5. `app/tests/test_config_service.py` — Unit tests
6. `test_step_e5_config_system.py` — Integration tests
7. `test_step_e5_backward_compat.py` — Backward compatibility tests

### MODIFIED Files:
1. `app/agents/validation_domain.py` — Use config service
2. `app/main.py` — Register admin API routes
3. `app/storage/mongo_client.py` — Add validation_config collection index creation

### DOCUMENTATION:
1. `STEP_E5_IMPLEMENTATION.md` — Full technical guide
2. `STEP_E5_QUICK_REFERENCE.md` — Developer reference

---

## Data Flow Diagram

```
Invoice Submission
│
├─ API receives: invoice_doc, org_id, region
│
├─ Orchestrator loads ConfigurationService
│  └─ (first call loads from DB, subsequent calls use 5-min cache)
│
├─ ValidationAgent calls ValidationDomain.run_validation(
│    db, invoice_doc, org_id, region, config_service
│  )
│
├─ ValidationDomain._validate_*_rules() functions:
│  ├─ Call: config = await config_service.get_rule_config(org_id, "E2-F1", region)
│  ├─ Use: tolerance = config['parameters']['tolerance_amount_cents']
│  └─ Fallback: Use hardcoded if config missing
│
├─ Validation rules apply org-specific thresholds
│
└─ Result: Invoice validated with organization's configuration
```

---

## API Usage Examples

### Example 1: Get current configuration for organization

```bash
curl -X GET "http://localhost:8001/api/v1/admin/validation-config?org_id=ORG-001&region=US" \
  -H "Authorization: Bearer admin_token"
```

**Response**:
```json
{
  "data": [
    {
      "rule_id": "E2-F1",
      "rule_name": "Amount Tolerance",
      "enabled": true,
      "parameters": {
        "tolerance_amount_cents": 100,
        "tolerance_percentage": 0.5
      },
      "updated_at": "2025-12-30T10:00:00Z"
    }
  ],
  "total": 11
}
```

### Example 2: Increase tolerance for year-end

```bash
curl -X PUT "http://localhost:8001/api/v1/admin/validation-config/E2-F1" \
  -H "Authorization: Bearer admin_token" \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "ORG-001",
    "region": "US",
    "parameters": {
      "tolerance_amount_cents": 500
    },
    "effective_from": "2025-12-20T00:00:00Z",
    "effective_to": "2026-01-10T23:59:59Z",
    "reason": "Year-end reconciliation period"
  }'
```

### Example 3: View configuration change history

```bash
curl -X GET "http://localhost:8001/api/v1/admin/validation-config/history?org_id=ORG-001&rule_id=E2-F1&days=30" \
  -H "Authorization: Bearer admin_token"
```

**Response**:
```json
{
  "data": [
    {
      "timestamp": "2025-12-30T10:00:00Z",
      "changed_by": "admin@company.com",
      "rule_id": "E2-F1",
      "field": "tolerance_amount_cents",
      "old_value": 100,
      "new_value": 500,
      "reason": "Year-end reconciliation period",
      "effective_period": "2025-12-20 to 2026-01-10"
    }
  ],
  "total": 1
}
```

---

## Success Criteria

✅ **Step E5 Complete When**:

1. **Configuration Service**:
   - `ConfigurationService` loads rules from MongoDB
   - Caching works (5-minute TTL, manual invalidation)
   - Fallback to hardcoded defaults works
   - All 11 rules (E1-E4) have default config in database

2. **Admin API**:
   - All 7 endpoints functional and tested
   - Authorization checks working
   - Configuration updates persisted to database
   - Audit trail recorded for all changes

3. **ValidationDomain Integration**:
   - Uses config service for all thresholds
   - Works with and without config service (backward compatible)
   - All hard-coded values extracted and configurable
   - Graceful fallback to defaults on config load failure

4. **Testing**:
   - Unit tests: 20+ tests for config service and validator
   - Integration tests: 15+ tests for API and validation
   - Backward compatibility: All E1-E4 tests pass unchanged
   - Multi-tenant tests: ORG isolation verified
   - Multi-region tests: Region fallback logic verified

5. **Documentation**:
   - `STEP_E5_IMPLEMENTATION.md` complete (technical guide)
   - `STEP_E5_QUICK_REFERENCE.md` complete (developer reference)
   - API documentation with examples
   - Configuration schema documented
   - Migration guide for existing deployments

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Config load fails → Validation uses old hardcoded | Medium | Graceful fallback to hardcoded defaults |
| Cache poisoning → Wrong config applied | High | Add config validation before cache write |
| Org A sees Org B config | Critical | Use organization_id in query filters + tests |
| API exposed without auth → Config modified by unauthorized | High | JWT/Bearer token validation on all endpoints |
| Config change breaks validation | Medium | Parameter validation + test suite |
| Database slow → Config lookup blocks validation | Medium | In-memory cache with 5-minute TTL |

---

## Migration Strategy

### For Existing Deployments:

1. **Deploy E5 code** (backward compatible, no config required)
2. **Seed database** with default configuration from hardcoded values
3. **Optional**: Migrate organization-specific settings via admin API
4. **No downtime**: Old deployments still work with hardcoded values

### For New Deployments:

1. Deploy E5 with empty validation_config collection
2. Run seed script to populate defaults
3. Admin configures organization-specific thresholds via API
4. Validation uses configured values

---

## Next Steps (E6+)

- **E6: Approval Workflows** — Use configuration to route approvals
- **E7: UI/Frontend** — Admin dashboard for configuration management
- **E8: Real-time Updates** — WebSocket for live configuration updates
- **E9: ML Integration** — Suggest configuration parameters based on patterns

---

## Summary of Step E5

**Purpose**: Make validation rules configurable without code changes

**Key Components**:
- ConfigurationService with caching and fallback
- Admin API for managing configuration
- MongoDB validation_config collection
- Complete audit trail of all changes
- Multi-tenant and multi-region support
- 100% backward compatible with E1-E4

**Implementation Path**:
1. Create config infrastructure (service, validator)
2. Modify ValidationDomain to use config
3. Create admin API endpoints
4. Write comprehensive tests
5. Seed database with defaults

**Test Coverage**: 35+ tests (unit + integration)  
**Expected Timeline**: 2-3 implementation sessions

