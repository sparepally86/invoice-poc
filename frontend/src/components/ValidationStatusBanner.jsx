import React from 'react';
import { AlertCircle, CheckCircle, XCircle } from 'lucide-react';

/**
 * ValidationStatusBanner - Displays validation status (PASS/WARN/FAIL) prominently
 * Shows status color, icon, message, and issue count
 */
export function ValidationStatusBanner({ validation }) {
  if (!validation) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center text-slate-600">
        <p className="text-sm">Validation pending...</p>
      </div>
    );
  }

  const status = validation.status || 'UNKNOWN';
  const totalIssues = (validation.issues || []).length;
  const hardFailures = (validation.issues || []).filter(i => i.severity === 'HARD').length;
  const softWarnings = (validation.issues || []).filter(i => i.severity === 'SOFT').length;

  let config = {
    color: 'bg-slate-50 border-slate-200',
    icon: AlertCircle,
    message: 'Validation status unknown',
    iconColor: 'text-slate-600'
  };

  if (status === 'PASS') {
    config = {
      color: 'bg-emerald-50 border-emerald-200',
      icon: CheckCircle,
      message: totalIssues === 0 ? 'No validation issues detected' : 'Validation passed',
      iconColor: 'text-emerald-600'
    };
  } else if (status === 'WARN') {
    config = {
      color: 'bg-amber-50 border-amber-200',
      icon: AlertCircle,
      message: `Invoice has ${softWarnings} warning${softWarnings !== 1 ? 's' : ''}`,
      iconColor: 'text-amber-600'
    };
  } else if (status === 'FAIL') {
    config = {
      color: 'bg-red-50 border-red-200',
      icon: XCircle,
      message: `Invoice has ${hardFailures} validation failure${hardFailures !== 1 ? 's' : ''}`,
      iconColor: 'text-red-600'
    };
  }

  const Icon = config.icon;

  return (
    <div className={`border rounded-lg p-4 ${config.color} flex items-start gap-3`}>
      <Icon className={`w-5 h-5 ${config.iconColor} flex-shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-slate-900">{status}</span>
          {totalIssues > 0 && (
            <span className={`text-xs font-medium px-2 py-1 rounded ${
              status === 'FAIL' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {totalIssues} {totalIssues === 1 ? 'issue' : 'issues'}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-700">{config.message}</p>
      </div>
    </div>
  );
}
