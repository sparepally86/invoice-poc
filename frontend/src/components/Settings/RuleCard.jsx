import React from 'react';
import { Edit2, Eye, History, MoreVertical, Power } from 'lucide-react';
import { getCategoryColor, formatParameterValue, RULE_METADATA } from '../../lib/api/validation-config';

/**
 * Individual rule card component for display in the grid
 */
const RuleCard = ({ rule, onEdit, onViewHistory, onDisable, onView }) => {
  const metadata = RULE_METADATA[rule.rule_id] || {};
  const hasParameters = Object.keys(metadata.parameters || {}).length > 0;

  const getSeverityColor = (severity) => {
    return severity === 'HARD' 
      ? 'bg-red-100 text-red-800'
      : 'bg-yellow-100 text-yellow-800';
  };

  const formatLastModified = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-slate-900">{rule.rule_id}</span>
            <span className={`px-2 py-1 text-xs font-medium rounded ${getCategoryColor(rule.rule_category)}`}>
              {rule.rule_category}
            </span>
            <span className={`px-2 py-1 text-xs font-medium rounded ${getSeverityColor(rule.severity || 'SOFT')}`}>
              {rule.severity || 'SOFT'}
            </span>
          </div>
          <h3 className="text-sm font-medium text-slate-700">{metadata.name || rule.rule_id}</h3>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          {rule.enabled ? (
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
          ) : (
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-600 mb-3">
        {metadata.description || 'Rule configuration management'}
      </p>

      {/* Current values display */}
      {hasParameters && rule.parameters && (
        <div className="mb-4 bg-slate-50 rounded p-3 space-y-1">
          {Object.entries(rule.parameters).map(([key, val]) => (
            <div key={key} className="text-xs flex items-center justify-between">
              <span className="text-slate-600">{key.replace(/_/g, ' ')}</span>
              <span className="font-mono text-slate-900">
                {formatParameterValue(key, val)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Metadata row */}
      <div className="text-xs text-slate-500 mb-4 border-t border-slate-100 pt-3">
        <div className="flex items-center justify-between">
          <span>
            Last Modified: {formatLastModified(rule.updated_at)}
          </span>
          {rule.changed_by && (
            <span>by {rule.changed_by}</span>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onView(rule)}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded hover:bg-slate-200 transition-colors"
          title="View details"
        >
          <Eye className="w-4 h-4" />
          View
        </button>

        {hasParameters && (
          <button
            onClick={() => onEdit(rule)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-100 rounded hover:bg-blue-200 transition-colors"
            title="Edit configuration"
          >
            <Edit2 className="w-4 h-4" />
            Edit
          </button>
        )}

        <button
          onClick={() => onViewHistory(rule)}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded hover:bg-slate-200 transition-colors"
          title="View change history"
        >
          <History className="w-4 h-4" />
          History
        </button>

        <button
          onClick={() => onDisable(rule)}
          className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded transition-colors ${
            rule.enabled
              ? 'text-red-700 bg-red-100 hover:bg-red-200'
              : 'text-green-700 bg-green-100 hover:bg-green-200'
          }`}
          title={rule.enabled ? 'Disable rule' : 'Enable rule'}
        >
          <Power className="w-4 h-4" />
          {rule.enabled ? 'Disable' : 'Enable'}
        </button>
      </div>
    </div>
  );
};

export default RuleCard;
