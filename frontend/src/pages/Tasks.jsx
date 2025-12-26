import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckSquare, RefreshCw, CheckCircle, XCircle, Eye, Edit3, Clock, AlertCircle, User, FileText } from "lucide-react";
import api from "../lib/api";

const TASK_TYPE_CONFIG = {
  approval: { label: "Approval", color: "bg-amber-100 text-amber-700", icon: Clock },
  exception: { label: "Exception", color: "bg-red-100 text-red-700", icon: AlertCircle },
  review: { label: "Review", color: "bg-blue-100 text-blue-700", icon: Eye },
};

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actioning, setActioning] = useState(null);
  const [message, setMessage] = useState(null);

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      const data = await api.getTasks();
      setTasks(Array.isArray(data) ? data : (data.items || []));
    } catch (e) {
      console.error(e);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleApprove(task) {
    if (!window.confirm("Approve this invoice?")) return;
    setActioning(task._id || task.id);
    setMessage(null);
    try {
      await api.approveInvoice(task.invoice_id, { approver: "ui:user", comment: "approved via UI" });
      setMessage({ type: "success", text: "Invoice approved successfully" });
      await load();
    } catch (e) {
      console.error(e);
      setMessage({ type: "error", text: "Approve failed: " + (e?.message || JSON.stringify(e)) });
    } finally {
      setActioning(null);
    }
  }

  async function handleReject(task) {
    if (!window.confirm("Reject this invoice?")) return;
    setActioning(task._id || task.id);
    setMessage(null);
    try {
      await api.rejectInvoice(task.invoice_id, { approver: "ui:user", comment: "rejected via UI" });
      setMessage({ type: "success", text: "Invoice rejected" });
      await load();
    } catch (e) {
      console.error(e);
      setMessage({ type: "error", text: "Reject failed: " + (e?.message || JSON.stringify(e)) });
    } finally {
      setActioning(null);
    }
  }

  const getTaskTypeBadge = (type) => {
    const config = TASK_TYPE_CONFIG[type] || { label: type, color: "bg-slate-100 text-slate-700", icon: CheckSquare };
    const Icon = config.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600">
            {tasks.length} pending {tasks.length === 1 ? "task" : "tasks"}
          </span>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Message */}
      {message && (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-lg ${
          message.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" : "bg-red-50 border border-red-200 text-red-700"
        }`}>
          {message.type === "success" ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          <span className="text-sm">{message.text}</span>
        </div>
      )}

      {/* Tasks Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Invoice</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Agent</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Created</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-500">
                      <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                      Loading tasks...
                    </div>
                  </td>
                </tr>
              ) : tasks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <CheckSquare className="w-12 h-12 text-slate-200" />
                      <div className="text-slate-500">No pending tasks</div>
                      <p className="text-sm text-slate-400">All caught up! Check back later for new tasks.</p>
                    </div>
                  </td>
                </tr>
              ) : tasks.map(t => (
                <tr key={t._id || t.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    {getTaskTypeBadge(t.type)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
                        <FileText className="w-4 h-4 text-slate-500" />
                      </div>
                      <Link
                        to={`/invoices/${encodeURIComponent(t.invoice_id)}`}
                        className="font-medium text-primary-600 hover:text-primary-700"
                      >
                        {t.invoice_id}
                      </Link>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 text-slate-600">
                      <User className="w-4 h-4 text-slate-400" />
                      <span className="text-sm">{t.payload?.agent || "-"}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">
                    {t.created_at || "-"}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      {t.type === "approval" ? (
                        <>
                          <button
                            onClick={() => handleApprove(t)}
                            disabled={actioning === (t._id || t.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                          >
                            <CheckCircle className="w-4 h-4" />
                            {actioning === (t._id || t.id) ? "..." : "Approve"}
                          </button>
                          <button
                            onClick={() => handleReject(t)}
                            disabled={actioning === (t._id || t.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
                          >
                            <XCircle className="w-4 h-4" />
                            {actioning === (t._id || t.id) ? "..." : "Reject"}
                          </button>
                        </>
                      ) : (
                        <>
                          <Link
                            to={`/invoices/${encodeURIComponent(t.invoice_id)}`}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                            Open
                          </Link>
                          <button
                            onClick={() => alert("Edit inline JSON not yet implemented")}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                          >
                            <Edit3 className="w-4 h-4" />
                            Edit
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        {tasks.length > 0 && (
          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200">
            <span className="text-sm text-slate-600">
              Showing {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
