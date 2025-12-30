import React, { useState, useEffect } from 'react';
import { X, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import ParameterInput from './ParameterInput';
import { RULE_METADATA, validateParameters } from '../../lib/api/validation-config';

/**
 * Modal for editing rule parameters
 */
const RuleEditor = ({ rule, onSave, onCancel, defaultValues }) => {
  const metadata = RULE_METADATA[rule.rule_id] || {};
  const [parameters, setParameters] = useState({});
  const [reason, setReason] = useState('');
  const [effectiveFrom, setEffectiveFrom] = useState('');
  const [effectiveTo, setEffectiveTo] = useState('');
  const [errors, setErrors] = useState({});
  const [validationErrors, setValidationErrors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [success, setSuccess] = useState('');

  useEffect(() => {
    // Initialize with current parameters or defaults
    if (rule.parameters) {
      setParameters(rule.parameters);
    } else if (defaultValues && defaultValues.parameters) {
      setParameters(defaultValues.parameters);
    }
  }, [rule, defaultValues]);

  const handleParameterChange = (name, value) => {
    setParameters(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = async () => {
    const newErrors = {};

    // Validate required fields
    if (!reason.trim()) {
      newErrors.reason = 'Change reason is required';
    }

    // Validate dates
    if (effectiveFrom && effectiveTo) {
      const from = new Date(effectiveFrom);
      const to = new Date(effectiveTo);
      if (from >= to) {
        newErrors.dates = 'End date must be after start date';
      }
    }

    // Validate parameters with backend
    if (Object.keys(metadata.parameters || {}).length > 0) {
      setValidating(true);
      try {
        const validation = await validateParameters(rule.rule_id, parameters);
        if (!validation.valid) {
          setValidationErrors(validation.errors);
          return false;
        }
        if (validation.warnings) {
          console.warn('Parameter warnings:', validation.warnings);
        }
      } catch (error) {
        newErrors.validation = `Validation failed: ${error.message}`;
      } finally {
        setValidating(false);
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!await validateForm()) {
      return;
    }

    setLoading(true);
    try {
      await onSave({
        parameters,
        reason,
        effective_from: effectiveFrom || undefined,
        effective_to: effectiveTo || undefined
      });
      setSuccess('Changes saved successfully!');
      setTimeout(() => {
        onCancel();
      }, 1500);
    } catch (error) {
      setErrors(prev => ({
        ...prev,
        save: error.message
      }));
    } finally {
      setLoading(false);
    }
  };

  const hasParameters = Object.keys(metadata.parameters || {}).length > 0;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{metadata.name}</h2>
            <p className="text-sm text-slate-600">{rule.rule_id}</p>
          </div>
          <button
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600"
            title="Close"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Description */}
          <div>
            <p className="text-sm text-slate-600">{metadata.description}</p>
          </div>

          {/* Success message */}
          {success && (
            <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* Validation errors */}
          {validationErrors.length > 0 && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <h4 className="font-medium text-red-900 mb-2">Validation Errors:</h4>
              <ul className="space-y-1">
                {validationErrors.map((error, idx) => (
                  <li key={idx} className="text-sm text-red-700">• {error}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Form errors */}
          {errors.save && (
            <div className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{errors.save}</span>
            </div>
          )}

          {/* Parameters */}
          {hasParameters && (
            <div className="border-t border-slate-200 pt-6">
              <h3 className="font-medium text-slate-900 mb-4">Parameters</h3>
              <div className="space-y-4">
                {Object.entries(metadata.parameters || {}).map(([key, spec]) => (
                  <ParameterInput
                    key={key}
                    name={key}
                    label={key.replace(/_/g, ' ').toUpperCase()}
                    type={spec.type}
                    value={parameters[key] ?? spec.default ?? ''}
                    onChange={handleParameterChange}
                    min={spec.min}
                    max={spec.max}
                    items={spec.items && spec.type === 'array' ? spec.items : []}
                    placeholder={String(spec.default ?? '')}
                    error={errors[key]}
                    required={true}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Change metadata */}
          <div className="border-t border-slate-200 pt-6">
            <h3 className="font-medium text-slate-900 mb-4">Change Information</h3>
            
            {/* Reason */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Reason for Change <span className="text-red-500">*</span>
              </label>
              <textarea
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  if (errors.reason) {
                    setErrors(prev => ({ ...prev, reason: '' }));
                  }
                }}
                placeholder="E.g., Year-end reconciliation, Regional expansion, Q4 adjustment"
                className={`w-full px-3 py-2 border rounded-lg text-sm ${
                  errors.reason
                    ? 'border-red-300 bg-red-50 focus:ring-red-500'
                    : 'border-slate-300 focus:ring-blue-500'
                } focus:outline-none focus:ring-1`}
                rows={3}
              />
              {errors.reason && <p className="mt-1 text-sm text-red-600">{errors.reason}</p>}
            </div>

            {/* Effective dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Effective From
                </label>
                <input
                  type="datetime-local"
                  value={effectiveFrom}
                  onChange={(e) => {
                    setEffectiveFrom(e.target.value);
                    if (errors.dates) {
                      setErrors(prev => ({ ...prev, dates: '' }));
                    }
                  }}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Effective To
                </label>
                <input
                  type="datetime-local"
                  value={effectiveTo}
                  onChange={(e) => {
                    setEffectiveTo(e.target.value);
                    if (errors.dates) {
                      setErrors(prev => ({ ...prev, dates: '' }));
                    }
                  }}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
            {errors.dates && <p className="mt-2 text-sm text-red-600">{errors.dates}</p>}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200 bg-slate-50">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading || validating}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {loading || validating ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RuleEditor;
