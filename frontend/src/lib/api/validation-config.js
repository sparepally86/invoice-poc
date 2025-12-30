/**
 * API client for validation configuration management
 * Communicates with /api/v1/admin/validation-config endpoints
 */

const API_BASE = 'http://localhost:8001/api/v1/admin/validation-config';

// Helper to get authorization token
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token') || 'demo_token';
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
};

/**
 * Get all configurations for an organization and region
 */
export const getConfigurations = async (orgId, region = 'US') => {
  try {
    const response = await fetch(
      `${API_BASE}?org_id=${orgId}&region=${region}`,
      { headers: getAuthHeaders() }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data.data || [];
  } catch (error) {
    console.error('Failed to fetch configurations:', error);
    throw error;
  }
};

/**
 * Get specific rule configuration
 */
export const getRuleConfig = async (ruleId, orgId, region = 'US') => {
  try {
    const response = await fetch(
      `${API_BASE}/${ruleId}?org_id=${orgId}&region=${region}`,
      { headers: getAuthHeaders() }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data.data || {};
  } catch (error) {
    console.error(`Failed to fetch rule config ${ruleId}:`, error);
    throw error;
  }
};

/**
 * Update rule configuration
 */
export const updateRuleConfig = async (ruleId, payload) => {
  try {
    const response = await fetch(
      `${API_BASE}/${ruleId}`,
      {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Failed to update rule ${ruleId}:`, error);
    throw error;
  }
};

/**
 * Disable rule for organization
 */
export const disableRule = async (ruleId, orgId, reason) => {
  try {
    const response = await fetch(
      `${API_BASE}/${ruleId}/disable`,
      {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ org_id: orgId, reason })
      }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Failed to disable rule ${ruleId}:`, error);
    throw error;
  }
};

/**
 * Get configuration change history
 */
export const getChangeHistory = async (orgId, options = {}) => {
  const { ruleId, days = 30 } = options;
  let url = `${API_BASE}/history?org_id=${orgId}&days=${days}`;
  if (ruleId) url += `&rule_id=${ruleId}`;
  
  try {
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data.data || [];
  } catch (error) {
    console.error('Failed to fetch change history:', error);
    throw error;
  }
};

/**
 * Validate parameters before saving
 */
export const validateParameters = async (ruleId, parameters) => {
  try {
    const response = await fetch(
      `${API_BASE}/validate`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ rule_id: ruleId, parameters })
      }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return {
      valid: data.valid,
      errors: data.errors || [],
      warnings: data.warnings || []
    };
  } catch (error) {
    console.error(`Failed to validate parameters for ${ruleId}:`, error);
    throw error;
  }
};

/**
 * Get hardcoded default configurations
 */
export const getDefaults = async (ruleId = null) => {
  let url = `${API_BASE}/defaults`;
  if (ruleId) url += `?rule_id=${ruleId}`;
  
  try {
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data.data || [];
  } catch (error) {
    console.error('Failed to fetch defaults:', error);
    throw error;
  }
};

/**
 * Rule metadata and schema definitions
 */
export const RULE_METADATA = {
  'E1-S1': {
    name: 'Invoice Number Required',
    category: 'STRUCTURAL',
    severity: 'HARD',
    description: 'Invoices must have a valid invoice number',
    parameters: {}
  },
  'E1-S2': {
    name: 'Required Fields Present',
    category: 'STRUCTURAL',
    severity: 'HARD',
    description: 'All required fields must be present',
    parameters: {}
  },
  'E1-S3': {
    name: 'Line Item Consistency',
    category: 'STRUCTURAL',
    severity: 'HARD',
    description: 'Line items must be consistent with header',
    parameters: {}
  },
  'E1-S4': {
    name: 'Numeric Fields Valid',
    category: 'STRUCTURAL',
    severity: 'HARD',
    description: 'All numeric fields must contain valid numbers',
    parameters: {}
  },
  'E2-F1': {
    name: 'Amount Tolerance',
    category: 'FINANCIAL',
    severity: 'SOFT',
    description: 'Set tolerance thresholds for invoice amounts',
    parameters: {
      tolerance_amount_cents: { type: 'integer', min: 1, max: 10000, default: 100 },
      tolerance_percentage: { type: 'float', min: 0, max: 100, default: 0.5 },
      warning_threshold_percentage: { type: 'float', min: 0, max: 100, default: 2.0 }
    }
  },
  'E2-F2': {
    name: 'Line Item Amount Validation',
    category: 'FINANCIAL',
    severity: 'SOFT',
    description: 'Validate individual line item amounts',
    parameters: {
      tolerance_percentage: { type: 'float', min: 0, max: 100, default: 0.5 }
    }
  },
  'E2-F3': {
    name: 'High Amount Threshold',
    category: 'FINANCIAL',
    severity: 'SOFT',
    description: 'Flag invoices exceeding a threshold amount',
    parameters: {
      high_amount_threshold: { type: 'integer', min: 100000, max: 10000000, default: 1000000 }
    }
  },
  'E2-F4': {
    name: 'Multi-Currency Sum Validation',
    category: 'FINANCIAL',
    severity: 'HARD',
    description: 'Validate multi-currency invoice sums',
    parameters: {}
  },
  'E3-P1': {
    name: 'Currency Validation',
    category: 'POLICY',
    severity: 'HARD',
    description: 'Validate allowed currencies by region',
    parameters: {
      allowed_currencies: { type: 'array', items: 'string', default: ['USD', 'EUR', 'GBP', 'CHF', 'CAD', 'AUD', 'JPY', 'INR'] }
    }
  },
  'E3-P2': {
    name: 'Vendor Approval Status',
    category: 'POLICY',
    severity: 'HARD',
    description: 'Require vendor approval before processing',
    parameters: {}
  },
  'E3-P3': {
    name: 'Invoice Date Validation',
    category: 'POLICY',
    severity: 'SOFT',
    description: 'Validate invoice dates are within acceptable window',
    parameters: {
      date_validation_window_days: { type: 'integer', min: 1, max: 365, default: 180 }
    }
  },
  'E3-P4': {
    name: 'Vendor Country Validation',
    category: 'POLICY',
    severity: 'HARD',
    description: 'Restrict vendors to allowed countries',
    parameters: {
      required_countries: { type: 'array', items: 'string', default: ['US', 'EU'] }
    }
  },
  'E4-D1': {
    name: 'Exact Match Duplicate Detection',
    category: 'DUPLICATE',
    severity: 'HARD',
    description: 'Detect exact duplicate invoices',
    parameters: {}
  },
  'E4-D2': {
    name: 'Time-Window Duplicate Detection',
    category: 'DUPLICATE',
    severity: 'SOFT',
    description: 'Detect duplicate invoices within time window',
    parameters: {
      time_window_days: { type: 'integer', min: 1, max: 365, default: 30 }
    }
  },
  'E4-D3': {
    name: 'Similar Amount Heuristic',
    category: 'DUPLICATE',
    severity: 'SOFT',
    description: 'Detect similar invoices by amount and date',
    parameters: {
      similar_amount_tolerance_pct: { type: 'float', min: 0, max: 100, default: 2.0 },
      time_window_days: { type: 'integer', min: 1, max: 365, default: 60 }
    }
  }
};

/**
 * Get category color for UI display
 */
export const getCategoryColor = (category) => {
  const colors = {
    'STRUCTURAL': 'bg-blue-100 text-blue-800',
    'FINANCIAL': 'bg-purple-100 text-purple-800',
    'POLICY': 'bg-orange-100 text-orange-800',
    'DUPLICATE': 'bg-pink-100 text-pink-800'
  };
  return colors[category] || 'bg-gray-100 text-gray-800';
};

/**
 * Format parameters for display
 */
export const formatParameterValue = (key, value) => {
  if (key.includes('percentage')) return `${value}%`;
  if (key.includes('cents')) return `$${(value / 100).toFixed(2)}`;
  if (key.includes('threshold')) return `$${(value / 100).toFixed(2)}`;
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
};
