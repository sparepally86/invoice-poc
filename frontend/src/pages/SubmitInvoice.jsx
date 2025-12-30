import React, { useEffect, useState, useRef } from "react";
import { Upload, Trash2, Shuffle, Send, CheckCircle, XCircle, Clock, AlertCircle, Zap, GitBranch, FileText, Wifi, WifiOff } from "lucide-react";
import { NegativeScenariosAccordion } from "../components/NegativeScenariosAccordion";
import { applyNegativeScenarios } from "../lib/invoice-scenarios";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "http://localhost:8000";

const STATUS_ICONS = {
  RECEIVED: { icon: FileText, color: "text-slate-600 bg-slate-100" },
  VALIDATED: { icon: CheckCircle, color: "text-primary-600 bg-primary-100" },
  MATCHED: { icon: Zap, color: "text-emerald-600 bg-emerald-100" },
  EXCEPTION: { icon: XCircle, color: "text-red-600 bg-red-100" },
  needs_human: { icon: AlertCircle, color: "text-amber-600 bg-amber-100" },
  APPROVAL_PENDING: { icon: Clock, color: "text-amber-600 bg-amber-100" },
  APPROVED: { icon: CheckCircle, color: "text-emerald-600 bg-emerald-100" },
  REJECTED: { icon: XCircle, color: "text-red-600 bg-red-100" },
  POSTED: { icon: CheckCircle, color: "text-green-600 bg-green-100" },
  UNKNOWN: { icon: AlertCircle, color: "text-slate-600 bg-slate-100" },
};

function InvoiceJourney({ invoiceId }) {
  const [steps, setSteps] = useState([]);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!invoiceId) return;

    if (esRef.current) {
      try { esRef.current.close(); } catch (e) {}
      esRef.current = null;
    }

    const url = `${BACKEND}/api/v1/invoices/${invoiceId}/events`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = (e) => {
      console.warn("SSE error", e);
      setConnected(false);
    };

    es.addEventListener("init", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        const wf = data?.workflow || {};
        setSteps(wf.steps || []);
        const last = (wf.steps || []).slice(-1)[0];
        setStatus(last?.status ?? last?.to ?? null);
      } catch (e) {
        console.warn("init parse error", e);
      }
    });

    es.addEventListener("step", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data?.step) {
          setSteps(prev => [...prev, data.step]);
          const s = data.step;
          const newStatus = s.type === "status_change" ? s.to : (s.status || s.result?.status || "UNKNOWN");
          setStatus(newStatus);
        }
      } catch (e) {
        console.warn("step parse error", e);
      }
    });

    es.addEventListener("deleted", (ev) => {
      setSteps(prev => [...prev, { agent: "system", status: "deleted", note: "Invoice document deleted" }]);
    });

    return () => {
      try { es.close(); } catch (e) {}
      esRef.current = null;
      setConnected(false);
    };
  }, [invoiceId]);

  useEffect(() => {
    const node = containerRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [steps]);

  function renderStep(s, idx) {
    const label = s.agent || s.type || s.result?.agent || "step";
    const t = s.status || (s.type === "status_change" && s.to) || s.result?.status || "UNKNOWN";
    const statusConfig = STATUS_ICONS[t] || STATUS_ICONS.UNKNOWN;
    const Icon = statusConfig.icon;
    const ts = s.timestamp || s.created_at || "";
    const short = s.note || s.result?.summary || (s.result?.issues && s.result.issues.length ? s.result.issues.map(i => i.code).join(", ") : "");
    
    return (
      <div key={idx} className="flex gap-4 py-4 border-b border-slate-100 last:border-0">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${statusConfig.color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-slate-900">{label}</span>
            <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-600 rounded">
              {t}
            </span>
          </div>
          {short && (
            <p className="text-sm text-slate-600 mb-1">{short}</p>
          )}
          {ts && (
            <p className="text-xs text-slate-400">{ts}</p>
          )}
        </div>
      </div>
    );
  }

  const currentStatusConfig = STATUS_ICONS[status] || STATUS_ICONS.UNKNOWN;
  const CurrentIcon = currentStatusConfig.icon;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="w-5 h-5 text-slate-400" />
          <h3 className="font-semibold text-slate-900">Invoice Journey</h3>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
          connected ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
        }`}>
          {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {connected ? "Live" : "Disconnected"}
        </div>
      </div>

      <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center gap-3">
        <span className="text-sm text-slate-600">Current Status:</span>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${currentStatusConfig.color}`}>
          <CurrentIcon className="w-4 h-4" />
          {status || "N/A"}
        </span>
      </div>

      <div ref={containerRef} className="max-h-96 overflow-y-auto px-6">
        {steps.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>No steps yet</p>
            <p className="text-sm">Submit an invoice to start processing</p>
          </div>
        ) : (
          steps.map((s, i) => renderStep(s, i))
        )}
      </div>
    </div>
  );
}


export default function SubmitInvoice() {
  const [mode, setMode] = useState("po");
  const [splitLineItem, setSplitLineItem] = useState(true);
  const [jsonText, setJsonText] = useState(`{
  "source": {
    "system": "UI",
    "received_at": "2025-01-01T10:00:00Z"
  },
  "document": {
    "image_url": "https://storage.example.com/invoice.pdf"
  },
  "header": {
    "invoice_number": "INV-001",
    "invoice_date": "2025-01-01",
    "vendor_name": "Vendor 1",
    "currency": "INR",
    "total_amount": 5000
  },
  "lines": [
    {
      "line_number": 1,
      "description": "Services provided",
      "quantity": 1,
      "line_amount": 5000
    }
  ]
}`);
  const [statusMsg, setStatusMsg] = useState(null);
  const [loadingGen, setLoadingGen] = useState(false);
  const [loadingSubmit, setLoadingSubmit] = useState(false);

  // Negative scenarios organized by category (Step E8)
  const [negativeScenarios, setNegativeScenarios] = useState({
    STRUCTURAL: [],
    FINANCIAL: [],
    POLICY: [],
    DUPLICATE: []
  });

  const [lastInvoiceId, setLastInvoiceId] = useState(null);

  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      const params = new URLSearchParams();
      params.append("mode", mode);
      if (splitLineItem) params.append("split_first_line", "true");

      const url = `${BACKEND}/api/v1/dev/generate-invoice?${params.toString()}`;
      const resp = await fetch(url, { method: "POST" });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setStatusMsg({ type: "error", text: `Generator error: ${JSON.stringify(data)}` });
        setLoadingGen(false);
        return;
      }
      const generated = data?.generated_invoice || data || {};
      
      // Apply negative scenarios (Step E8)
      const mutated = applyNegativeScenarios(generated, negativeScenarios);

      setJsonText(JSON.stringify(mutated, null, 2));
      
      const scenarioCount = 
        negativeScenarios.STRUCTURAL.length +
        negativeScenarios.FINANCIAL.length +
        negativeScenarios.POLICY.length +
        negativeScenarios.DUPLICATE.length;
      
      const scenarioText = scenarioCount > 0 ? ` with ${scenarioCount} scenarios` : '';
      setStatusMsg({ type: "success", text: `Generated invoice (${mode === "po" ? "PO-based" : "Non-PO"})${scenarioText}` });
    } catch (err) {
      console.error(err);
      setStatusMsg({ type: "error", text: `Error generating invoice: ${err?.message || JSON.stringify(err)}` });
    } finally {
      setLoadingGen(false);
    }
  }

  async function handleSubmitInvoice() {
    setStatusMsg(null);
    setLoadingSubmit(true);
    setLastInvoiceId(null);
    try {
      const json = JSON.parse(jsonText);
      const url = `${BACKEND}/api/v1/invoices/submit`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(json),
      });

      const resp = await r.json().catch(() => ({}));
      if (!r.ok) {
        setStatusMsg({ type: "error", text: `Submit error: ${JSON.stringify(resp)}` });
      } else {
        const invoiceId = resp.invoice_id || resp._id || resp.id || (json && json._id) || null;
        if (invoiceId) {
          setLastInvoiceId(invoiceId);
          setStatusMsg({ type: "success", text: `Submitted — invoice_id: ${invoiceId}` });
        } else {
          setStatusMsg({ type: "success", text: `Submitted — response: ${JSON.stringify(resp)}` });
        }
      }
    } catch (err) {
      console.error(err);
      setStatusMsg({ type: "error", text: "Submit error: " + (err?.message || JSON.stringify(err)) });
    } finally {
      setLoadingSubmit(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* LEFT: Generate + Submit panel */}
      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3">
            <Upload className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-slate-900">Submit Invoice</h3>
          </div>
          
          <div className="p-6 space-y-6">
            {/* Invoice Type */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Invoice Type</label>
              <div className="flex gap-4">
                <label className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer border-2 transition-colors ${
                  mode === "po" ? "border-primary-500 bg-primary-50" : "border-slate-200 hover:border-slate-300"
                }`}>
                  <input
                    type="radio"
                    name="mode"
                    value="po"
                    checked={mode === "po"}
                    onChange={() => setMode("po")}
                    className="w-4 h-4 text-primary-600"
                  />
                  <span className="text-sm font-medium text-slate-700">PO-based</span>
                </label>
                <label className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer border-2 transition-colors ${
                  mode === "nonpo" ? "border-primary-500 bg-primary-50" : "border-slate-200 hover:border-slate-300"
                }`}>
                  <input
                    type="radio"
                    name="mode"
                    value="nonpo"
                    checked={mode === "nonpo"}
                    onChange={() => setMode("nonpo")}
                    className="w-4 h-4 text-primary-600"
                  />
                  <span className="text-sm font-medium text-slate-700">Non-PO based</span>
                </label>
              </div>
            </div>

            {/* Options */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Options</label>
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={splitLineItem}
                    onChange={(e) => setSplitLineItem(e.target.checked)}
                    className="w-4 h-4 text-primary-600 rounded"
                  />
                  <span className="text-sm text-slate-600">Split line item</span>
                </label>
                <button
                  onClick={handleGenerate}
                  disabled={loadingGen}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50 transition-colors"
                >
                  <Shuffle className="w-4 h-4" />
                  {loadingGen ? "Generating..." : "Generate"}
                </button>
              </div>
            </div>

            {/* Test Scenarios */}
            <div className="space-y-4">
              <NegativeScenariosAccordion 
                value={negativeScenarios}
                onChange={setNegativeScenarios}
              />
            </div>

            {/* Invoice JSON */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Invoice JSON</label>
              <textarea
                rows={14}
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                className="w-full px-4 py-3 text-sm font-mono bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                placeholder="Enter invoice JSON..."
              />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSubmitInvoice}
                disabled={loadingSubmit}
                className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                <Send className="w-4 h-4" />
                {loadingSubmit ? "Submitting..." : "Submit Invoice"}
              </button>
              <button
                onClick={() => { setJsonText("{}"); setStatusMsg({ type: "info", text: "Cleared" }); setLastInvoiceId(null); }}
                className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear
              </button>
            </div>

            {/* Status Message */}
            {statusMsg && (
              <div className={`flex items-center gap-3 px-4 py-3 rounded-lg ${
                statusMsg.type === "error" ? "bg-red-50 border border-red-200 text-red-700" :
                statusMsg.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" :
                "bg-slate-50 border border-slate-200 text-slate-700"
              }`}>
                {statusMsg.type === "error" ? <XCircle className="w-5 h-5" /> :
                 statusMsg.type === "success" ? <CheckCircle className="w-5 h-5" /> :
                 <AlertCircle className="w-5 h-5" />}
                <span className="text-sm">{statusMsg.text}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* RIGHT: Live Journey */}
      <div className="lg:sticky lg:top-6">
        {lastInvoiceId ? (
          <InvoiceJourney invoiceId={lastInvoiceId} />
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3">
              <GitBranch className="w-5 h-5 text-slate-400" />
              <h3 className="font-semibold text-slate-900">Invoice Journey</h3>
            </div>
            <div className="p-12 text-center">
              <FileText className="w-16 h-16 mx-auto mb-4 text-slate-200" />
              <h4 className="font-medium text-slate-700 mb-2">No Invoice Submitted</h4>
              <p className="text-sm text-slate-500">
                Generate and submit an invoice to view its live processing journey here.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
