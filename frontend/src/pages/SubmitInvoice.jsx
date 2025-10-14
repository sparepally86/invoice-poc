// frontend/src/pages/SubmitInvoice.jsx
import React, { useEffect, useState, useRef } from "react";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

/**
 * Inline InvoiceJourney component — listens to SSE and renders steps.
 */
function InvoiceJourney({ invoiceId }) {
  const [steps, setSteps] = useState([]);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const containerRef = useRef(null);

  const STATUS_EMOJI = {
    RECEIVED: "📥",
    VALIDATED: "✅",
    MATCHED: "🔗",
    EXCEPTION: "❌",
    needs_human: "🧑‍🤝‍🧑",
    APPROVAL_PENDING: "⏳",
    APPROVED: "🎉",
    REJECTED: "😞",
    POSTED: "🚀",
    UNKNOWN: "🔔",
  };

  useEffect(() => {
    if (!invoiceId) return;

    // close any previous ES
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

  // auto-scroll when steps change
  useEffect(() => {
    const node = containerRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [steps]);

  function renderStep(s, idx) {
    const label = s.agent || s.type || s.result?.agent || "step";
    const t = s.status || (s.type === "status_change" && s.to) || s.result?.status || "UNKNOWN";
    const emoji = STATUS_EMOJI[t] || STATUS_EMOJI.UNKNOWN;
    const ts = s.timestamp || s.created_at || "";
    const short = s.note || s.result?.summary || (s.result?.issues && s.result.issues.length ? s.result.issues.map(i => i.code).join(", ") : "");
    return (
      <div key={idx} style={{ 
        display: "flex", 
        gap: 16, 
        alignItems: "flex-start", 
        padding: "12px 0", 
        borderBottom: "1px solid var(--secondary-200)"
      }}>
        <div style={{ 
          fontSize: 24, 
          width: 40, 
          height: 40,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--secondary-100)",
          borderRadius: "8px"
        }}>
          {emoji}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ 
            fontWeight: 600,
            color: "var(--secondary-900)",
            marginBottom: 4
          }}>
            {label} 
            <span style={{ 
              color: "var(--secondary-500)", 
              fontSize: 12, 
              fontWeight: 500,
              background: "var(--secondary-100)",
              padding: "2px 6px",
              borderRadius: "4px",
              marginLeft: 8
            }}>
              {t}
            </span>
          </div>
          {short && (
            <div style={{ 
              color: "var(--secondary-700)", 
              fontSize: 14,
              marginBottom: 4,
              lineHeight: 1.4
            }}>
              {short}
            </div>
          )}
          {ts && (
            <div style={{ 
              color: "var(--secondary-500)", 
              fontSize: 12
            }}>
              {ts}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 className="card-title">📊 Invoice Journey</h3>
          <div style={{ 
            fontSize: 12, 
            fontWeight: 600,
            color: connected ? "var(--success-700)" : "var(--error-700)",
            background: connected ? "var(--success-100)" : "var(--error-100)",
            padding: "4px 8px",
            borderRadius: "4px"
          }}>
            {connected ? "🟢 Live" : "🔴 Disconnected"}
          </div>
        </div>
      </div>

      <div className="card-body" style={{ padding: 0 }}>
        <div style={{ 
          padding: "16px 24px",
          borderBottom: "1px solid var(--secondary-200)",
          background: "var(--secondary-50)"
        }}>
          <strong>Current Status: </strong> 
          <span style={{
            color: "var(--secondary-800)",
            background: "var(--secondary-200)",
            padding: "4px 8px",
            borderRadius: "4px",
            fontSize: 14,
            fontWeight: 500
          }}>
            {status || "N/A"} {STATUS_EMOJI[status] || STATUS_EMOJI.UNKNOWN}
          </span>
        </div>

        <div ref={containerRef} style={{ 
          maxHeight: 420, 
          overflowY: "auto",
          padding: "0 24px"
        }}>
          {steps.length === 0 && (
            <div style={{ 
              color: "var(--secondary-500)",
              textAlign: "center",
              padding: 32,
              fontStyle: "italic"
            }}>
              No steps yet — submit invoice to start processing.
            </div>
          )}
          {steps.map((s, i) => renderStep(s, i))}
          {steps.length > 0 && <div style={{ height: 16 }}></div>}
        </div>
      </div>
    </div>
  );
}


/* ------- Main SubmitInvoice page component ------- */
export default function SubmitInvoice() {
  const [mode, setMode] = useState("po");
  const [splitLineItem, setSplitLineItem] = useState(true);
  const [jsonText, setJsonText] = useState(`{
  "header": {
    "invoice_ref": "TEST-1",
    "invoice_date": "2025-10-10",
    "vendor_number": "V0001",
    "vendor_name": "Vendor 1",
    "currency": "INR",
    "amount": 1000
  },
  "items": []
}`);
  const [statusMsg, setStatusMsg] = useState(null);
  const [loadingGen, setLoadingGen] = useState(false);
  const [loadingSubmit, setLoadingSubmit] = useState(false);

  const [missMandatory, setMissMandatory] = useState(false);
  const [badVendor, setBadVendor] = useState(false);
  const [badPO, setBadPO] = useState(false);

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
        setStatusMsg(`Generator error: ${JSON.stringify(data)}`);
        setLoadingGen(false);
        return;
      }
      const generated = data?.generated_invoice || data || {};
      const mutated = JSON.parse(JSON.stringify(generated));

      if (missMandatory) {
        if (mutated.header) {
          delete mutated.header.invoice_ref;
        }
      }

      if (badVendor) {
        if (!mutated.header) mutated.header = {};
        mutated.header.vendor_number = "BAD-VENDOR-9999";
        mutated.header.vendor_name = "NonExistent Vendor";
        if (mutated.vendor) {
          mutated.vendor.vendor_id = "BAD-VENDOR-9999";
          mutated.vendor.name_raw = "NonExistent Vendor";
        }
      }

      if (badPO) {
        if (!mutated.header) mutated.header = {};
        mutated.header.po_number = "PO-BAD-000";
        if (mutated.items && mutated.items.length > 0) {
          mutated.items[0].amount = (mutated.items[0].amount || 0) + 123.45;
        }
      }

      setJsonText(JSON.stringify(mutated, null, 2));
      setStatusMsg(`Generated invoice (${mode === "po" ? "PO-based" : "Non-PO"})`);
    } catch (err) {
      console.error(err);
      setStatusMsg(`Error generating invoice: ${err?.message || JSON.stringify(err)}`);
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
      const url = `${BACKEND}/api/v1/incoming`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(json),
      });

      const resp = await r.json().catch(() => ({}));
      if (!r.ok) {
        setStatusMsg(`Submit error: ${JSON.stringify(resp)}`);
      } else {
        const invoiceId = resp.invoice_id || resp._id || resp.id || (json && json._id) || null;
        if (invoiceId) {
          setLastInvoiceId(invoiceId);
          setStatusMsg(`Submitted — invoice_id: ${invoiceId}`);
        } else {
          setStatusMsg(`Submitted — response: ${JSON.stringify(resp)}`);
        }
      }
    } catch (err) {
      console.error(err);
      setStatusMsg("Submit error: " + (err?.message || JSON.stringify(err)));
    } finally {
      setLoadingSubmit(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>
      {/* LEFT: Generate + Submit panel */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460 }}>
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">📤 Submit Invoice</h2>
          </div>
          <div className="card-body">
            <div className="form-group">
              <div className="form-label">Invoice Type</div>
              <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                <label style={{ 
                  display: "flex", 
                  gap: 8, 
                  alignItems: "center",
                  padding: "8px 12px",
                  background: mode === "po" ? "var(--primary-100)" : "var(--secondary-100)",
                  borderRadius: "6px",
                  cursor: "pointer",
                  border: `2px solid ${mode === "po" ? "var(--primary-300)" : "transparent"}`
                }}>
                  <input type="radio" name="mode" value="po" checked={mode === "po"} onChange={() => setMode("po")} />
                  PO-based
                </label>

                <label style={{ 
                  display: "flex", 
                  gap: 8, 
                  alignItems: "center",
                  padding: "8px 12px",
                  background: mode === "nonpo" ? "var(--primary-100)" : "var(--secondary-100)",
                  borderRadius: "6px",
                  cursor: "pointer",
                  border: `2px solid ${mode === "nonpo" ? "var(--primary-300)" : "transparent"}`
                }}>
                  <input type="radio" name="mode" value="nonpo" checked={mode === "nonpo"} onChange={() => setMode("nonpo")} />
                  Non-PO based
                </label>
              </div>
            </div>

            <div className="form-group">
              <div className="form-label">Options</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={splitLineItem} onChange={(e) => setSplitLineItem(e.target.checked)} />
                  Split line item
                </label>

                <button 
                  onClick={handleGenerate} 
                  disabled={loadingGen} 
                  className="btn btn-secondary"
                  style={{ marginLeft: "auto" }}
                >
                  {loadingGen ? "Generating..." : "🎲 Generate"}
                </button>
              </div>
            </div>

            <div className="form-group">
              <div className="form-label">Test Scenarios</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={missMandatory} onChange={(e) => setMissMandatory(e.target.checked)} />
                  Miss mandatory field
                </label>

                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={badVendor} onChange={(e) => setBadVendor(e.target.checked)} />
                  Bad vendor
                </label>

                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={badPO} onChange={(e) => setBadPO(e.target.checked)} />
                  Bad PO match
                </label>
              </div>
            </div>

            <div className="form-group">
              <div className="form-label">Invoice JSON</div>
              <textarea
                rows={16}
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                className="form-textarea"
              />
            </div>

            <div className="flex gap-4 items-center">
              <button 
                onClick={handleSubmitInvoice} 
                disabled={loadingSubmit} 
                className="btn btn-primary"
              >
                {loadingSubmit ? "Submitting..." : "🚀 Submit Invoice"}
              </button>

              <button
                onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); setLastInvoiceId(null); }}
                className="btn btn-secondary"
              >
                🗑️ Clear
              </button>
            </div>

            {statusMsg && (
              <div className={`alert ${statusMsg.startsWith("Error") || statusMsg.includes("error") ? "alert-error" : "alert-success"}`}>
                {statusMsg}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* RIGHT: Live Journey */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460, position: "sticky", top: 20 }}>
        {lastInvoiceId ? (
          <InvoiceJourney invoiceId={lastInvoiceId} />
        ) : (
          <div className="card">
            <div className="card-body text-center" style={{ padding: 48 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🧾</div>
              <h3 style={{ color: "var(--secondary-600)", margin: 0 }}>Invoice Journey</h3>
              <p style={{ color: "var(--secondary-500)", margin: "8px 0 0 0" }}>
                Generate and submit an invoice to view its live processing journey here.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
