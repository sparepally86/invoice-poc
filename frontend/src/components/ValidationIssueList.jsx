import React, { useState } from 'react';
import { ChevronDown, AlertCircle, AlertTriangle, Info } from 'lucide-react';

/**
 * ValidationIssueList - Displays validation issues grouped by category
 * Shows code, message, field, severity, and category
 */
export function ValidationIssueList({ validation }) {
  const [expandedCategories, setExpandedCategories] = useState({
    STRUCTURAL: true,
    FINANCIAL: true,
    POLICY: false,
    DUPLICATE: false
  });

  if (!validation || !validation.issues || validation.issues.length === 0) {
    return null;
  }

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Group issues by category
  const issuesByCategory = {
    STRUCTURAL: validation.issues.filter(i => i.category === 'STRUCTURAL'),
    FINANCIAL: validation.issues.filter(i => i.category === 'FINANCIAL'),
    POLICY: validation.issues.filter(i => i.category === 'POLICY'),
    DUPLICATE: validation.issues.filter(i => i.category === 'DUPLICATE')
  };

  // Category configuration
  const categoryConfig = {
    STRUCTURAL: {
      label: 'Structural Rules',
      color: 'blue',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
      headerColor: 'bg-blue-100 text-blue-900',
      description: 'Schema and format validation issues'
    },
    FINANCIAL: {
      label: 'Financial Rules',
      color: 'purple',
      bgColor: 'bg-purple-50',
      borderColor: 'border-purple-200',
      headerColor: 'bg-purple-100 text-purple-900',
      description: 'Amount and calculation validation issues'
    },
    POLICY: {
      label: 'Policy Rules',
      color: 'orange',
      bgColor: 'bg-orange-50',
      borderColor: 'border-orange-200',
      headerColor: 'bg-orange-100 text-orange-900',
      description: 'Business rule validation issues'
    },
    DUPLICATE: {
      label: 'Duplicate / Risk Rules',
      color: 'pink',
      bgColor: 'bg-pink-50',
      borderColor: 'border-pink-200',
      headerColor: 'bg-pink-100 text-pink-900',
      description: 'Risk and duplicate detection issues'
    }
  };

  const getSeverityIcon = (severity) => {
    return severity === 'HARD' ? (
      <AlertCircle className="w-4 h-4 text-red-600" />
    ) : (
      <AlertTriangle className="w-4 h-4 text-amber-600" />
    );
  };

  const getSeverityColor = (severity) => {
    return severity === 'HARD'
      ? 'bg-red-100 text-red-700 border-red-200'
      : 'bg-amber-100 text-amber-700 border-amber-200';
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
        <h3 className="font-semibold text-slate-900">Validation Issues</h3>
        <p className="text-sm text-slate-600 mt-1">
          {validation.issues.length} {validation.issues.length === 1 ? 'issue' : 'issues'} found
        </p>
      </div>

      {/* Issues by Category */}
      <div className="divide-y divide-slate-200">
        {Object.entries(issuesByCategory).map(([categoryKey, issues]) => {
          if (issues.length === 0) return null;

          const category = categoryConfig[categoryKey];
          const isExpanded = expandedCategories[categoryKey];

          return (
            <div key={categoryKey} className="border-b border-slate-200 last:border-b-0">
              {/* Category Header */}
              <button
                onClick={() => toggleCategory(categoryKey)}
                className={`w-full px-6 py-4 flex items-center justify-between ${category.headerColor} hover:opacity-90 transition-opacity`}
              >
                <div className="flex items-center gap-3 flex-1">
                  <ChevronDown
                    className={`w-5 h-5 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  />
                  <div className="text-left">
                    <div className="font-semibold">{category.label}</div>
                    <div className="text-xs opacity-75">{issues.length} {issues.length === 1 ? 'issue' : 'issues'}</div>
                  </div>
                </div>
              </button>

              {/* Issues List */}
              {isExpanded && (
                <div className={`${category.bgColor} ${category.borderColor} border-l-4 space-y-3 p-4`}>
                  {issues.map((issue, idx) => (
                    <div key={idx} className="bg-white rounded border border-slate-200 p-4">
                      {/* Issue Header */}
                      <div className="flex items-start gap-3 mb-2">
                        {getSeverityIcon(issue.severity)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono text-xs font-semibold text-slate-600">
                              {issue.code}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded border ${getSeverityColor(issue.severity)}`}>
                              {issue.severity}
                            </span>
                          </div>
                          <p className="text-sm text-slate-900 font-medium">{issue.message}</p>
                        </div>
                      </div>

                      {/* Issue Details */}
                      <div className="ml-7 space-y-2">
                        {issue.field && (
                          <div className="text-xs text-slate-600">
                            <span className="font-medium">Field:</span> <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">{issue.field}</code>
                          </div>
                        )}
                        {issue.metadata && Object.keys(issue.metadata).length > 0 && (
                          <div className="text-xs text-slate-600">
                            <span className="font-medium">Details:</span>
                            <div className="mt-1 space-y-1">
                              {Object.entries(issue.metadata).map(([key, value]) => (
                                <div key={key} className="text-slate-600">
                                  <span className="text-slate-500">{key}:</span> <span className="font-mono">{String(value)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
