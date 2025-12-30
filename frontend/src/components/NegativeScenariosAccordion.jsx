import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { NEGATIVE_SCENARIOS, getCategoryColor, getCategoryHeaderColor } from '../lib/invoice-scenarios';

/**
 * NegativeScenariosAccordion - Category-based test scenario selector
 * Groups negative test scenarios by validation category (STRUCTURAL, FINANCIAL, POLICY, DUPLICATE)
 * Allows multi-select across categories
 */
export function NegativeScenariosAccordion({ value = {}, onChange }) {
  const [expandedCategories, setExpandedCategories] = useState({
    STRUCTURAL: true,
    FINANCIAL: true,
    POLICY: false,
    DUPLICATE: false
  });

  // Ensure value has all categories
  const normalizedValue = {
    STRUCTURAL: value.STRUCTURAL || [],
    FINANCIAL: value.FINANCIAL || [],
    POLICY: value.POLICY || [],
    DUPLICATE: value.DUPLICATE || []
  };

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  const toggleScenario = (category, scenarioKey) => {
    const current = normalizedValue[category] || [];
    const newScenarios = current.includes(scenarioKey)
      ? current.filter(s => s !== scenarioKey)
      : [...current, scenarioKey];

    onChange({
      ...normalizedValue,
      [category]: newScenarios
    });
  };

  const getSelectedCount = (category) => {
    return (normalizedValue[category] || []).length;
  };

  const getTotalCount = (category) => {
    return Object.keys(NEGATIVE_SCENARIOS[category].scenarios || {}).length;
  };

  return (
    <div className="space-y-3 w-full">
      <div className="text-sm font-semibold text-gray-700 mb-4">
        Test Scenarios (Select negative cases to inject)
      </div>

      {Object.entries(NEGATIVE_SCENARIOS).map(([categoryKey, categoryData]) => {
        const isExpanded = expandedCategories[categoryKey];
        const selectedCount = getSelectedCount(categoryKey);
        const totalCount = getTotalCount(categoryKey);
        const headerColor = getCategoryHeaderColor(categoryKey);
        const contentColor = getCategoryColor(categoryKey);

        return (
          <div key={categoryKey} className="border rounded-lg overflow-hidden bg-white">
            {/* Category Header */}
            <button
              onClick={() => toggleCategory(categoryKey)}
              className={`w-full px-4 py-3 flex items-center justify-between ${headerColor} hover:opacity-90 transition-opacity`}
            >
              <div className="flex items-center gap-3 flex-1">
                <ChevronDown
                  size={18}
                  className={`transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                />
                <div className="text-left">
                  <div className="font-semibold">{categoryData.label}</div>
                  <div className="text-xs opacity-75">
                    {selectedCount} of {totalCount} selected
                  </div>
                </div>
              </div>
              <div className="text-xs font-semibold px-2 py-1 bg-white rounded opacity-75">
                {selectedCount}/{totalCount}
              </div>
            </button>

            {/* Category Content */}
            {isExpanded && (
              <div className={`p-4 space-y-3 ${contentColor} border-t`}>
                {Object.entries(categoryData.scenarios).map(([scenarioKey, scenarioData]) => {
                  const isSelected = (normalizedValue[categoryKey] || []).includes(scenarioKey);

                  return (
                    <label
                      key={scenarioKey}
                      className="flex items-start gap-3 p-2 rounded hover:bg-white/50 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleScenario(categoryKey, scenarioKey)}
                        className="mt-1 w-4 h-4 rounded"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm">{scenarioData.label}</div>
                        <div className="text-xs opacity-75 break-words">
                          {scenarioData.description}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {/* Summary */}
      {(normalizedValue.STRUCTURAL?.length > 0 ||
        normalizedValue.FINANCIAL?.length > 0 ||
        normalizedValue.POLICY?.length > 0 ||
        normalizedValue.DUPLICATE?.length > 0) && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-900">
          <span className="font-semibold">
            {normalizedValue.STRUCTURAL?.length +
              normalizedValue.FINANCIAL?.length +
              normalizedValue.POLICY?.length +
              normalizedValue.DUPLICATE?.length}{' '}
            scenarios
          </span>{' '}
          selected - invoice will include these negative cases
        </div>
      )}
    </div>
  );
}
