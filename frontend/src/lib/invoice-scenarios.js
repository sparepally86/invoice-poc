/**
 * Negative Test Scenarios for Invoice Generator
 * Organized by validation category (E1-E4)
 */

export const NEGATIVE_SCENARIOS = {
  STRUCTURAL: {
    label: 'Structural Rules',
    color: 'blue',
    scenarios: {
      EMPTY_DESCRIPTION: {
        label: 'Empty line description',
        description: 'Set line description to empty string'
      },
      DUPLICATE_LINE_NUMBER: {
        label: 'Duplicate line numbers',
        description: 'Duplicate a line_number in the invoice'
      },
      HEADER_NO_LINES: {
        label: 'Header total with no lines',
        description: 'Create header with total but empty line items'
      },
      ZERO_QUANTITY: {
        label: 'Zero or negative quantity',
        description: 'Set line quantity to 0 or negative value'
      },
      MISSING_MANDATORY_FIELD: {
        label: 'Missing mandatory field',
        description: 'Remove invoice_number from header'
      }
    }
  },

  FINANCIAL: {
    label: 'Financial Rules',
    color: 'purple',
    scenarios: {
      TOTAL_MISMATCH: {
        label: 'Header vs line total mismatch',
        description: 'Mismatch between header.total_amount and line sum'
      },
      TAX_MISMATCH: {
        label: 'Tax total mismatch',
        description: 'Set tax_amount inconsistent with lines'
      },
      DISCOUNT_MISMATCH: {
        label: 'Discount math mismatch',
        description: 'Discount doesn\'t match invoice calculation'
      },
      HIGH_AMOUNT: {
        label: 'High amount invoice',
        description: 'Set invoice total above $1,000,000 threshold'
      },
      NEGATIVE_AMOUNT: {
        label: 'Negative invoice amount',
        description: 'Set total_amount to negative value'
      }
    }
  },

  POLICY: {
    label: 'Policy Rules',
    color: 'orange',
    scenarios: {
      UNSUPPORTED_CURRENCY: {
        label: 'Unsupported currency',
        description: 'Use currency not in allowed list'
      },
      FUTURE_DATE: {
        label: 'Invoice date in future',
        description: 'Set invoice_date to future date'
      },
      EXPIRED_DATE: {
        label: 'Invoice too old',
        description: 'Set invoice_date > 180 days in past'
      },
      MISSING_COUNTRY: {
        label: 'Missing country-specific fields',
        description: 'Remove country code from vendor'
      },
      UNAPPROVED_VENDOR: {
        label: 'Unapproved vendor',
        description: 'Use vendor not in approved list'
      }
    }
  },

  DUPLICATE: {
    label: 'Duplicate / Risk Rules',
    color: 'pink',
    scenarios: {
      EXACT_DUPLICATE: {
        label: 'Exact duplicate invoice',
        description: 'Reuse same vendor + invoice_number'
      },
      TIME_WINDOW_DUPLICATE: {
        label: 'Same amount within time window',
        description: 'Create invoice same amount as recent invoice'
      },
      SIMILAR_AMOUNT_HEURISTIC: {
        label: 'Similar amount heuristic',
        description: 'Create invoice with similar amount (±2%) within 60 days'
      },
      SUSPICIOUS_PATTERN: {
        label: 'Suspicious round amount',
        description: 'Use round number that appears multiple times'
      }
    }
  }
};

/**
 * Apply mutations to invoice based on selected scenarios
 */
export function applyNegativeScenarios(invoice, selectedScenarios) {
  const mutated = JSON.parse(JSON.stringify(invoice));

  // STRUCTURAL mutations
  if (selectedScenarios.STRUCTURAL?.includes('EMPTY_DESCRIPTION')) {
    if (mutated.lines && mutated.lines.length > 0) {
      mutated.lines[0].description = '';
    }
  }

  if (selectedScenarios.STRUCTURAL?.includes('DUPLICATE_LINE_NUMBER')) {
    if (mutated.lines && mutated.lines.length > 1) {
      mutated.lines[1].line_number = mutated.lines[0].line_number;
    }
  }

  if (selectedScenarios.STRUCTURAL?.includes('HEADER_NO_LINES')) {
    mutated.lines = [];
  }

  if (selectedScenarios.STRUCTURAL?.includes('ZERO_QUANTITY')) {
    if (mutated.lines && mutated.lines.length > 0) {
      mutated.lines[0].quantity = 0;
    }
  }

  if (selectedScenarios.STRUCTURAL?.includes('MISSING_MANDATORY_FIELD')) {
    if (mutated.header) {
      delete mutated.header.invoice_number;
    }
  }

  // FINANCIAL mutations
  if (selectedScenarios.FINANCIAL?.includes('TOTAL_MISMATCH')) {
    if (mutated.header && mutated.lines) {
      const lineSum = mutated.lines.reduce((sum, ln) => sum + (ln.line_amount || 0), 0);
      mutated.header.total_amount = lineSum + 999.99;
    }
  }

  if (selectedScenarios.FINANCIAL?.includes('TAX_MISMATCH')) {
    if (mutated.header) {
      mutated.header.tax_amount = (mutated.header.tax_amount || 0) + 500.00;
    }
  }

  if (selectedScenarios.FINANCIAL?.includes('DISCOUNT_MISMATCH')) {
    if (mutated.header) {
      mutated.header.discount_amount = (mutated.header.discount_amount || 0) + 250.00;
    }
  }

  if (selectedScenarios.FINANCIAL?.includes('HIGH_AMOUNT')) {
    if (mutated.header) {
      mutated.header.total_amount = 2000000.00;
    }
  }

  if (selectedScenarios.FINANCIAL?.includes('NEGATIVE_AMOUNT')) {
    if (mutated.header) {
      mutated.header.total_amount = -1000.00;
    }
  }

  // POLICY mutations
  if (selectedScenarios.POLICY?.includes('UNSUPPORTED_CURRENCY')) {
    if (mutated.header) {
      mutated.header.currency = 'XYZ'; // Invalid currency code
    }
  }

  if (selectedScenarios.POLICY?.includes('FUTURE_DATE')) {
    if (mutated.header) {
      const future = new Date();
      future.setDate(future.getDate() + 30);
      mutated.header.invoice_date = future.toISOString().split('T')[0];
    }
  }

  if (selectedScenarios.POLICY?.includes('EXPIRED_DATE')) {
    if (mutated.header) {
      const past = new Date();
      past.setDate(past.getDate() - 200);
      mutated.header.invoice_date = past.toISOString().split('T')[0];
    }
  }

  if (selectedScenarios.POLICY?.includes('MISSING_COUNTRY')) {
    if (mutated.header && mutated.header.vendor) {
      delete mutated.header.vendor.country_code;
    }
  }

  if (selectedScenarios.POLICY?.includes('UNAPPROVED_VENDOR')) {
    if (mutated.header) {
      mutated.header.vendor_name = 'Unapproved Vendor XYZ';
    }
  }

  // DUPLICATE mutations
  if (selectedScenarios.DUPLICATE?.includes('EXACT_DUPLICATE')) {
    // Keep same vendor + invoice number
    // This creates an exact duplicate when submitted
    if (mutated.header) {
      // Don't modify - let it remain identical to a previous invoice
    }
  }

  if (selectedScenarios.DUPLICATE?.includes('TIME_WINDOW_DUPLICATE')) {
    // Create same amount as recent invoice
    if (mutated.header) {
      mutated.header.total_amount = 5000.00; // Common amount
    }
  }

  if (selectedScenarios.DUPLICATE?.includes('SIMILAR_AMOUNT_HEURISTIC')) {
    // Create similar amount (±2%) within 60 days
    if (mutated.header && mutated.header.total_amount) {
      const current = mutated.header.total_amount;
      mutated.header.total_amount = current * 1.01; // 1% different
    }
  }

  if (selectedScenarios.DUPLICATE?.includes('SUSPICIOUS_PATTERN')) {
    if (mutated.header) {
      mutated.header.total_amount = 10000.00; // Round suspicious amount
    }
  }

  return mutated;
}

/**
 * Get category color for UI display
 */
export function getCategoryColor(category) {
  const colors = {
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    purple: 'bg-purple-50 border-purple-200 text-purple-900',
    orange: 'bg-orange-50 border-orange-200 text-orange-900',
    pink: 'bg-pink-50 border-pink-200 text-pink-900'
  };
  return colors[NEGATIVE_SCENARIOS[category]?.color] || colors.blue;
}

/**
 * Get category header color
 */
export function getCategoryHeaderColor(category) {
  const colors = {
    blue: 'bg-blue-100 text-blue-900',
    purple: 'bg-purple-100 text-purple-900',
    orange: 'bg-orange-100 text-orange-900',
    pink: 'bg-pink-100 text-pink-900'
  };
  return colors[NEGATIVE_SCENARIOS[category]?.color] || colors.blue;
}
