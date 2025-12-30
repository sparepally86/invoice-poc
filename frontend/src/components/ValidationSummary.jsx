import React, { useState } from 'react';
import { ChevronDown, AlertCircle, AlertTriangle } from 'lucide-react';

/**
 * ValidationSummary - Collapsible section showing validation summary counts
 * Displays hard failures and soft warnings with counts
 */
export function ValidationSummary({ validation }) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!validation || validation.status === 'PASS') {
    return null;
  }

  const hardFailures = (validation.issues || []).filter(i => i.severity === 'HARD').length;
  const softWarnings = (validation.issues || []).filter(i => i.severity === 'SOFT').length;
  const summary = validation.summary || {};

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <h3 className="font-semibold text-slate-900">Validation Summary</h3>
        <ChevronDown
          className={`w-5 h-5 text-slate-400 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 space-y-4">
          {/* Hard Failures Row */}
          <div className="flex items-start gap-3 pb-4 border-b border-slate-200">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-medium text-slate-900">Hard Failures</div>
              <p className="text-sm text-slate-600 mt-1">
                {hardFailures === 0
                  ? 'No hard validation failures'
                  : `${hardFailures} hard failure${hardFailures !== 1 ? 's' : ''} must be resolved`}
              </p>
            </div>
            <span className="text-lg font-bold text-red-600">{hardFailures}</span>
          </div>

          {/* Soft Warnings Row */}
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-medium text-slate-900">Soft Warnings</div>
              <p className="text-sm text-slate-600 mt-1">
                {softWarnings === 0
                  ? 'No soft validation warnings'
                  : `${softWarnings} soft warning${softWarnings !== 1 ? 's' : ''} detected`}
              </p>
            </div>
            <span className="text-lg font-bold text-amber-600">{softWarnings}</span>
          </div>
        </div>
      )}
    </div>
  );
}
