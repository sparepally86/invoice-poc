import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, Info } from 'lucide-react';

/**
 * Reusable parameter input component for validation rule configuration
 * Handles integers, floats, arrays (multi-select), and text
 */
const ParameterInput = ({
  name,
  label,
  type = 'text',
  value,
  onChange,
  error,
  onBlur,
  min,
  max,
  items = [],
  placeholder,
  help,
  required = false,
  disabled = false
}) => {
  const [touched, setTouched] = useState(false);
  const [localValue, setLocalValue] = useState(value);
  const [isValid, setIsValid] = useState(true);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const validateInput = (val) => {
    if (required && !val) return false;
    if (type === 'integer' || type === 'float') {
      const num = parseFloat(val);
      if (isNaN(num)) return false;
      if (min !== undefined && num < min) return false;
      if (max !== undefined && num > max) return false;
    }
    return true;
  };

  const handleChange = (e) => {
    const newValue = type === 'integer' 
      ? parseInt(e.target.value) || '' 
      : type === 'float'
      ? parseFloat(e.target.value) || ''
      : e.target.value;
    
    setLocalValue(newValue);
    const valid = validateInput(newValue);
    setIsValid(valid);
    onChange(name, newValue);
  };

  const handleBlur = () => {
    setTouched(true);
    if (onBlur) onBlur();
  };

  const handleArrayChange = (item) => {
    const arr = Array.isArray(localValue) ? localValue : [];
    const newArr = arr.includes(item)
      ? arr.filter(i => i !== item)
      : [...arr, item];
    setLocalValue(newArr);
    onChange(name, newArr);
  };

  const handleRemoveArrayItem = (item) => {
    const arr = Array.isArray(localValue) ? localValue : [];
    const newArr = arr.filter(i => i !== item);
    setLocalValue(newArr);
    onChange(name, newArr);
  };

  if (type === 'array') {
    return (
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-1">
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
        
        {/* Display selected items as tags */}
        <div className="flex flex-wrap gap-2 mb-3">
          {Array.isArray(localValue) && localValue.map(item => (
            <div
              key={item}
              className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
            >
              {item}
              <button
                type="button"
                onClick={() => handleRemoveArrayItem(item)}
                className="ml-1 hover:text-blue-900"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* Multi-select dropdown */}
        <div className="space-y-2">
          {items.map(item => (
            <label key={item} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={Array.isArray(localValue) && localValue.includes(item)}
                onChange={() => handleArrayChange(item)}
                className="w-4 h-4 rounded border-slate-300"
                disabled={disabled}
              />
              <span className="text-sm text-slate-700">{item}</span>
            </label>
          ))}
        </div>

        {help && (
          <div className="mt-2 flex items-start gap-2 text-xs text-slate-500">
            <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{help}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>

      <div className="relative">
        <input
          type={type === 'integer' || type === 'float' ? 'number' : 'text'}
          name={name}
          value={localValue}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder={placeholder}
          disabled={disabled}
          step={type === 'float' ? '0.01' : '1'}
          min={min}
          max={max}
          className={`w-full px-3 py-2 border rounded-lg text-sm font-mono ${
            disabled
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
              : error && touched
              ? 'border-red-300 bg-red-50 focus:ring-red-500'
              : isValid && touched
              ? 'border-green-300 bg-green-50 focus:ring-green-500'
              : 'border-slate-300 focus:ring-blue-500'
          } focus:outline-none focus:ring-1`}
        />

        {/* Validation indicators */}
        {touched && !error && isValid && (
          <CheckCircle className="absolute right-3 top-2.5 w-5 h-5 text-green-500" />
        )}
        {(error || (touched && !isValid)) && (
          <AlertCircle className="absolute right-3 top-2.5 w-5 h-5 text-red-500" />
        )}
      </div>

      {/* Constraints info */}
      {(min !== undefined || max !== undefined) && (
        <div className="mt-1 text-xs text-slate-500">
          Constraints: 
          {min !== undefined && ` min=${min}`}
          {min !== undefined && max !== undefined && ','}
          {max !== undefined && ` max=${max}`}
        </div>
      )}

      {/* Error message */}
      {(error || (touched && !isValid)) && (
        <p className="mt-1 text-sm text-red-600">
          {error || 'Invalid value'}
        </p>
      )}

      {/* Help text */}
      {help && !error && (
        <div className="mt-2 flex items-start gap-2 text-xs text-slate-500">
          <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{help}</span>
        </div>
      )}
    </div>
  );
};

export default ParameterInput;
