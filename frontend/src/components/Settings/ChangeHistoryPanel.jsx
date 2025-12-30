import React, { useState, useEffect } from 'react';
import { X, Loader, AlertCircle, Filter } from 'lucide-react';
import { getChangeHistory } from '../../lib/api/validation-config';

/**
 * Change history panel showing audit trail for configuration changes
 */
const ChangeHistoryPanel = ({ rule, orgId, onClose }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(30);
  const [filterField, setFilterField] = useState(null);

  useEffect(() => {
    loadHistory();
  }, [rule, orgId, days]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await getChangeHistory(orgId, {
        ruleId: rule.rule_id,
        days
      });
      setHistory(data);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const formatValue = (field, value) => {
    if (typeof value === 'string' && value.endsWith('%')) {
      return value;
    }
    if (typeof value === 'number' && field.includes('cents')) {
      return `$${(value / 100).toFixed(2)}`;
    }
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    return String(value);
  };

  // Get unique fields from history
  const uniqueFields = [...new Set(history.map(h => h.field_changed))];

  // Filter history by field
  const filteredHistory = filterField
    ? history.filter(h => h.field_changed === filterField)
    : history;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Change History</h2>
            <p className="text-sm text-slate-600">{rule.rule_id} - {rule.rule_name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            title="Close"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Filters */}
        <div className="p-4 border-b border-slate-200 bg-slate-50 space-y-3">
          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <label className="text-sm font-medium text-slate-700 mr-2">Time Period:</label>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="px-3 py-1 border border-slate-300 rounded text-sm"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last 365 days</option>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700 mr-2">Field:</label>
              <select
                value={filterField || ''}
                onChange={(e) => setFilterField(e.target.value || null)}
                className="px-3 py-1 border border-slate-300 rounded text-sm"
              >
                <option value="">All fields</option>
                {uniqueFields.map(field => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader className="w-8 h-8 text-slate-400 animate-spin mb-2" />
              <p className="text-sm text-slate-500">Loading change history...</p>
            </div>
          ) : error ? (
            <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <div>
                <p className="font-medium">Failed to load history</p>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          ) : filteredHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-slate-500">No changes found</p>
              <p className="text-xs text-slate-400 mt-1">
                {filterField ? 'No changes to this field' : 'No changes in this time period'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredHistory.map((entry, idx) => (
                <div key={idx} className="border border-slate-200 rounded-lg p-4 hover:bg-slate-50 transition-colors">
                  {/* Timeline dot and line */}
                  <div className="flex gap-4">
                    {/* Timeline marker */}
                    <div className="flex flex-col items-center">
                      <div className="w-3 h-3 bg-blue-500 rounded-full border-4 border-white"></div>
                      {idx < filteredHistory.length - 1 && (
                        <div className="w-1 h-12 bg-blue-200 mt-2 mb-2"></div>
                      )}
                    </div>

                    {/* Change details */}
                    <div className="flex-1 pt-0.5">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-medium text-slate-900">
                            {entry.field_changed} Changed
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            {formatDate(entry.timestamp)}
                          </p>
                        </div>
                        <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-1 rounded">
                          by {entry.changed_by || 'System'}
                        </span>
                      </div>

                      {/* Change details */}
                      <div className="mt-3 space-y-2 bg-slate-50 rounded p-3">
                        <div className="grid grid-cols-2 gap-4 text-sm font-mono">
                          <div>
                            <span className="text-slate-500 text-xs">Previous Value:</span>
                            <p className="text-slate-900">
                              {formatValue(entry.field_changed, entry.old_value)}
                            </p>
                          </div>
                          <div>
                            <span className="text-slate-500 text-xs">New Value:</span>
                            <p className="text-slate-900">
                              {formatValue(entry.field_changed, entry.new_value)}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Reason */}
                      {entry.reason && (
                        <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-900">
                          <span className="font-medium">Reason:</span> {entry.reason}
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="mt-3 flex gap-2">
                        <button
                          className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 transition-colors disabled:opacity-50"
                          disabled
                          title="Revert functionality coming in E7.2"
                        >
                          Revert (Coming Soon)
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-200 bg-slate-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChangeHistoryPanel;
