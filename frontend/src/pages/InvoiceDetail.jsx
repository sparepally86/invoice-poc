import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle, XCircle, FileText, Calendar, Building2, Hash, DollarSign, Clock, GitBranch, ChevronDown, ChevronUp } from "lucide-react";
import api from "../lib/api";
import ExplanationPanel from "../components/ExplanationPanel";

const STATUS_CONFIG = {
  RECEIVED: { label: "Received", color: "bg-slate-100 text-slate-700" },
  VALIDATED: { label: "Validated", color: "bg-primary-100 text-primary-700" },
  MATCHED: { label: "Matched", color: "bg-emerald-100 text-emerald-700" },
  CODED: { label: "Coded", color: "bg-purple-100 text-purple-700" },
  PENDING_APPROVAL: { label: "Pending Approval", color: "bg-amber-100 text-amber-700" },
  APPROVED: { label: "Approved", color: "bg-emerald-100 text-emerald-700" },
  READY_FOR_POSTING: { label: "Ready for Posting", color: "bg-teal-100 text-teal-700" },
  POSTED: { label: "Posted", color: "bg-green-100 text-green-700" },
  EXCEPTION: { label: "Exception", color: "bg-red-100 text-red-700" },
  REJECTED: { label: "Rejected", color: "bg-red-100 text-red-700" },
};

export default function InvoiceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState(false);
  const [msg, setMsg] = useState(null);
  const [showJson, setShowJson] = useState(false);
  const [activeTab, setActiveTab] = useState("details");
  const [copyFeedback, setCopyFeedback] = useState(false);

  const copyToClipboard = () => {
    const jsonText = JSON.stringify(invoice, null, 2);
    navigator.clipboard.writeText(jsonText).then(() => {
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2000);
    }).catch(err => console.error("Failed to copy:", err));
  };

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setMsg(null);
      try {
        const doc = await api.getInvoice(id);
        if (!cancelled) setInvoice(doc);
      } catch (err) {
        console.error("getInvoice error", err);
        setMsg("Failed to load invoice: " + (err?.response?.data || err?.message || JSON.stringify(err)));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, [id]);

  async function doApprove() {
    if (!confirm("Approve this invoice?")) return;
    setActioning(true);
    setMsg(null);
    try {
      const resp = await api.approveInvoice(id, { approver: "ui:user", comment: "Approved via UI" });
      setMsg({ type: "success", text: "Invoice approved successfully" });
      const doc = await api.getInvoice(id);
      setInvoice(doc);
    } catch (err) {
      console.error("approve error", err);
      setMsg({ type: "error", text: "Approve failed: " + (err?.response?.data || err?.message) });
    } finally {
      setActioning(false);
    }
  }

  async function doReject() {
    if (!confirm("Reject this invoice?")) return;
    setActioning(true);
    setMsg(null);
    try {
      const resp = await api.rejectInvoice(id, { approver: "ui:user", comment: "Rejected via UI" });
      setMsg({ type: "success", text: "Invoice rejected" });
      const doc = await api.getInvoice(id);
      setInvoice(doc);
    } catch (err) {
      console.error("reject error", err);
      setMsg({ type: "error", text: "Reject failed: " + (err?.response?.data || err?.message) });
    } finally {
      setActioning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-slate-500">
          <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
          Loading invoice...
        </div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
        <div className="text-slate-500 mb-4">Invoice not found</div>
        <button
          onClick={() => navigate("/invoices")}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-600 hover:bg-primary-50 rounded-lg"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Invoices
        </button>
      </div>
    );
  }

  const header = invoice.header || {};
  const items = invoice.items || invoice.lines || [];
  const statusConfig = STATUS_CONFIG[invoice.status] || { label: invoice.status, color: "bg-slate-100 text-slate-700" };
  const canAction = invoice.status !== "READY_FOR_POSTING" && invoice.status !== "REJECTED" && invoice.status !== "POSTED";

  const tabs = [
    { id: "details", label: "Invoice Details" },
    { id: "items", label: `Line Items (${items.length})` },
    { id: "workflow", label: "Workflow" },
  ];

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/invoices")}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-semibold text-slate-900">
                {invoice._id || header.invoice_ref}
              </h2>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusConfig.color}`}>
                {statusConfig.label}
              </span>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              {header.vendor_name || invoice.vendor?.name_raw || "Unknown Vendor"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={doApprove}
            disabled={actioning || !canAction}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            {actioning ? "Processing..." : "Approve"}
          </button>
          <button
            onClick={doReject}
            disabled={actioning || !canAction}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <XCircle className="w-4 h-4" />
            {actioning ? "Processing..." : "Reject"}
          </button>
        </div>
      </div>

      {/* Message */}
      {msg && (
        <div className={`px-4 py-3 rounded-lg flex items-center gap-3 ${
          msg.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-800" : "bg-red-50 border border-red-200 text-red-800"
        }`}>
          {msg.type === "success" ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          <span className="text-sm">{msg.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Tabs */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="border-b border-slate-200">
              <div className="flex">
                {tabs.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab.id
                        ? "border-primary-500 text-primary-600"
                        : "border-transparent text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-6">
              {activeTab === "details" && (
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <FileText className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">Invoice Reference</div>
                        <div className="font-medium text-slate-900">{header.invoice_ref || invoice._id}</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Calendar className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">Invoice Date</div>
                        <div className="font-medium text-slate-900">{header.invoice_date || "-"}</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Building2 className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">Vendor</div>
                        <div className="font-medium text-slate-900">{header.vendor_name || invoice.vendor?.name_raw || "-"}</div>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Hash className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">PO Number</div>
                        <div className="font-medium text-primary-600">{header.po_number || header.po || "-"}</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <DollarSign className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">Amount</div>
                        <div className="font-medium text-slate-900">
                          {header.currency || "USD"} ${(header.amount ?? header.grand_total?.value ?? 0).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Clock className="w-5 h-5 text-slate-500" />
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider">Status</div>
                        <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${statusConfig.color}`}>
                          {statusConfig.label}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "items" && (
                <div>
                  {items.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">No line items</div>
                  ) : (
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-200">
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">#</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Description</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {items.map((it, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="px-4 py-3 text-sm text-slate-500">{idx + 1}</td>
                            <td className="px-4 py-3 text-sm text-slate-900">{it.item_text || it.description || it.name || "-"}</td>
                            <td className="px-4 py-3 text-sm text-slate-900 text-right font-medium">
                              ${(it.amount ?? it.total ?? 0).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {activeTab === "workflow" && (
                <div className="space-y-4">
                  {Array.isArray(invoice._workflow?.steps) && invoice._workflow.steps.length > 0 ? (
                    invoice._workflow.steps.slice().reverse().map((s, i) => (
                      <div key={i} className="flex gap-4">
                        <div className="flex flex-col items-center">
                          <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
                            <GitBranch className="w-4 h-4 text-primary-600" />
                          </div>
                          {i < invoice._workflow.steps.length - 1 && (
                            <div className="w-0.5 h-full bg-slate-200 my-2"></div>
                          )}
                        </div>
                        <div className="flex-1 pb-4">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-slate-900">{s.agent || s.type || "Step"}</span>
                            <span className="text-xs text-slate-500">{s.status || ""}</span>
                          </div>
                          <div className="text-xs text-slate-500 mb-2">{s.timestamp || s.ts || s.created_at}</div>
                          <pre className="text-xs bg-slate-50 rounded-lg p-3 overflow-auto max-h-32">
                            {JSON.stringify(s.result || s, null, 2)}
                          </pre>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-slate-500">No workflow steps recorded</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* JSON Toggle */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 flex items-center justify-between border-b border-slate-200 hover:bg-slate-50 transition-colors">
              <button
                onClick={() => setShowJson(!showJson)}
                className="flex-1 flex items-center justify-between text-left"
              >
                <span className="font-medium text-slate-700">Raw JSON Data</span>
                {showJson ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
              </button>
              {showJson && (
                <button
                  onClick={copyToClipboard}
                  className="ml-3 px-3 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
                  title="Copy JSON to clipboard"
                >
                  {copyFeedback ? "✓ Copied!" : "Copy"}
                </button>
              )}
            </div>
            {showJson && (
              <div className="px-6 pb-6">
                <pre className="text-xs bg-slate-50 rounded-lg p-4 overflow-auto max-h-80 font-mono">
                  {JSON.stringify(invoice, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {invoice && invoice._id && (
            <ExplanationPanel invoiceId={invoice._id} />
          )}
        </div>
      </div>
    </div>
  );
}
