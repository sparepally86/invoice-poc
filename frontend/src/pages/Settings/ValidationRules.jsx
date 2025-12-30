import React, { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw, Sliders } from 'lucide-react';
import RulesGrid from '../../components/Settings/RulesGrid';
import RuleEditor from '../../components/Settings/RuleEditor';
import ChangeHistoryPanel from '../../components/Settings/ChangeHistoryPanel';
import {
  getConfigurations,
  getRuleConfig,
  updateRuleConfig,
  disableRule,
  getDefaults,
  RULE_METADATA
} from '../../lib/api/validation-config';

/**
 * Main page for managing validation rule configurations
 * Accessible from Settings menu
 */
const ValidationRulesPage = () => {
  const [orgId, setOrgId] = useState('ORG-001');
  const [region, setRegion] = useState('US');
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingRule, setEditingRule] = useState(null);
  const [viewingHistory, setViewingHistory] = useState(null);
  const [viewingDetails, setViewingDetails] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [defaults, setDefaults] = useState({});

  // Sample organizations (in real app, fetch from API)
  const organizations = ['ORG-001', 'ORG-002', 'ORG-003'];
  const regions = ['US', 'EU', 'APAC', 'ALL'];

  useEffect(() => {
    loadRules();
    loadDefaults();
  }, [orgId, region]);

  const loadRules = async () => {
    setLoading(true);
    try {
      const data = await getConfigurations(orgId, region);
      
      // Merge with metadata to ensure all rules are displayed
      const allRules = Object.keys(RULE_METADATA).map(ruleId => {
        const existing = data.find(r => r.rule_id === ruleId);
        return existing || {
          rule_id: ruleId,
          rule_name: RULE_METADATA[ruleId].name,
          rule_category: RULE_METADATA[ruleId].category,
          severity: RULE_METADATA[ruleId].severity,
          enabled: true,
          parameters: RULE_METADATA[ruleId].parameters || {},
          organization_id: orgId,
          region: region
        };
      });

      setRules(allRules);
      setError('');
    } catch (err) {
      setError(`Failed to load rules: ${err.message}`);
      // Fallback: show all rules with defaults
      const fallbackRules = Object.keys(RULE_METADATA).map(ruleId => ({
        rule_id: ruleId,
        rule_name: RULE_METADATA[ruleId].name,
        rule_category: RULE_METADATA[ruleId].category,
        severity: RULE_METADATA[ruleId].severity,
        enabled: true,
        parameters: RULE_METADATA[ruleId].parameters || {},
        organization_id: orgId,
        region: region
      }));
      setRules(fallbackRules);
    } finally {
      setLoading(false);
    }
  };

  const loadDefaults = async () => {
    try {
      const data = await getDefaults();
      const defaultsMap = {};
      data.forEach(d => {
        defaultsMap[d.rule_id] = d;
      });
      setDefaults(defaultsMap);
    } catch (err) {
      console.error('Failed to load defaults:', err);
    }
  };

  const handleEditRule = (rule) => {
    setEditingRule(rule);
  };

  const handleViewHistory = (rule) => {
    setViewingHistory(rule);
  };

  const handleViewDetails = (rule) => {
    setViewingDetails(rule);
  };

  const handleDisableRule = async (rule) => {
    const newStatus = rule.enabled ? 'disable' : 'enable';
    const confirmed = window.confirm(
      `Are you sure you want to ${newStatus} ${rule.rule_id}? This affects all invoices processed after the change.`
    );

    if (!confirmed) return;

    try {
      await disableRule(rule.rule_id, orgId, `${newStatus === 'disable' ? 'Disabled' : 'Enabled'} via UI`);
      
      // Update local state
      setRules(prev => prev.map(r => 
        r.rule_id === rule.rule_id 
          ? { ...r, enabled: !r.enabled }
          : r
      ));

      setSuccessMessage(`Rule ${newStatus}d successfully`);
      setTimeout(() => setSuccessMessage(''), 3000);
      
      // Reload to get fresh data
      loadRules();
    } catch (err) {
      setError(`Failed to ${newStatus} rule: ${err.message}`);
    }
  };

  const handleSaveRule = async (payload) => {
    try {
      await updateRuleConfig(editingRule.rule_id, {
        org_id: orgId,
        region: region,
        ...payload
      });

      setSuccessMessage(`${editingRule.rule_id} updated successfully`);
      setTimeout(() => setSuccessMessage(''), 3000);
      setEditingRule(null);
      
      // Reload rules
      loadRules();
    } catch (err) {
      throw new Error(`Failed to save rule: ${err.message}`);
    }
  };

  return (
    <div className="flex-1 bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex items-start justify-between mb-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Sliders className="w-8 h-8 text-blue-600" />
                <h1 className="text-3xl font-bold text-slate-900">Validation Rules</h1>
              </div>
              <p className="text-slate-600">
                Manage financial, policy, and duplicate detection thresholds
              </p>
            </div>
            <button
              onClick={loadRules}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-5 h-5" />
              Refresh
            </button>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Organization
              </label>
              <select
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                className="px-4 py-2 border border-slate-300 rounded-lg font-medium bg-white cursor-pointer"
              >
                {organizations.map(org => (
                  <option key={org} value={org}>{org}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Region
              </label>
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="px-4 py-2 border border-slate-300 rounded-lg font-medium bg-white cursor-pointer"
              >
                {regions.map(reg => (
                  <option key={reg} value={reg}>{reg}</option>
                ))}
              </select>
            </div>

            <div className="flex-1" />

            <div>
              <p className="text-sm text-slate-600">
                <strong>Resolution Order:</strong> {orgId} + {region} → {orgId} + ALL → Hardcoded
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Success message */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 flex items-center gap-3">
            <div className="w-2 h-2 bg-green-600 rounded-full"></div>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="mb-6 flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <div>
              <p className="font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Rules Grid */}
        <RulesGrid
          rules={rules}
          loading={loading}
          error={error}
          onEdit={handleEditRule}
          onViewHistory={handleViewHistory}
          onDisable={handleDisableRule}
          onView={handleViewDetails}
          orgId={orgId}
          region={region}
        />
      </div>

      {/* Edit Modal */}
      {editingRule && (
        <RuleEditor
          rule={editingRule}
          onSave={handleSaveRule}
          onCancel={() => setEditingRule(null)}
          defaultValues={defaults[editingRule.rule_id]}
        />
      )}

      {/* History Modal */}
      {viewingHistory && (
        <ChangeHistoryPanel
          rule={viewingHistory}
          orgId={orgId}
          onClose={() => setViewingHistory(null)}
        />
      )}

      {/* Details View Modal (placeholder for future) */}
      {viewingDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full p-6">
            <h2 className="text-lg font-semibold mb-4">{viewingDetails.rule_id}</h2>
            <p className="text-slate-600 mb-4">{RULE_METADATA[viewingDetails.rule_id]?.description}</p>
            
            {Object.keys(viewingDetails.parameters || {}).length > 0 && (
              <div className="mb-6">
                <h3 className="font-medium mb-3">Current Parameters</h3>
                <div className="space-y-2 bg-slate-50 p-4 rounded">
                  {Object.entries(viewingDetails.parameters).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-slate-600">{key}</span>
                      <span className="font-mono text-slate-900">{String(val)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => setViewingDetails(null)}
              className="w-full px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ValidationRulesPage;
