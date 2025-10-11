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
      <div key={idx} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "8px 0", borderBottom: "1px solid #f6f6f6" }}>
        <div style={{ fontSize: 20 }}>{emoji}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{label} <span style={{ color: "#666", fontSize: 12 }}>· {t}</span></div>
          <div style={{ color: "#444", fontSize: 13 }}>{short}</div>
          <div style={{ color: "#999", fontSize: 12 }}>{ts}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Invoice journey</h3>
        <div style={{ fontSize: 13, color: connected ? "#059669" : "#b91c1c" }}>{connected ? "Live" : "Disconnected"}</div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <strong>Current status: </strong> {status || "N/A"} &nbsp; <span>{STATUS_EMOJI[status] || STATUS_EMOJI.UNKNOWN}</span>
      </div>

      <div ref={containerRef} style={{ maxHeight: 420, overflowY: "auto" }}>
        {steps.length === 0 && <div style={{ color: "#666" }}>No steps yet — submit invoice to start processing.</div>}
        {steps.map((s, i) => renderStep(s, i))}
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
    <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
      {/* LEFT: Generate + Submit panel */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460 }}>
        <h1>Submit Invoice (Capture simulation)</h1>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", marginBottom: 12 }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="radio" name="mode" value="po" checked={mode === "po"} onChange={() => setMode("po")} />
            PO-based (backend chooses random PO if none specified)
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="radio" name="mode" value="nonpo" checked={mode === "nonpo"} onChange={() => setMode("nonpo")} />
            Non-PO based
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: 12 }}>
            <input type="checkbox" checked={splitLineItem} onChange={(e) => setSplitLineItem(e.target.checked)} />
            Split line item
          </label>

          <button onClick={handleGenerate} disabled={loadingGen} style={{ marginLeft: "auto" }}>
            {loadingGen ? "Generating..." : "Generate"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 18, marginBottom: 12 }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={missMandatory} onChange={(e) => setMissMandatory(e.target.checked)} />
            Miss mandatory field
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={badVendor} onChange={(e) => setBadVendor(e.target.checked)} />
            Bad / missing vendor
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={badPO} onChange={(e) => setBadPO(e.target.checked)} />
            Bad / mismatched PO
          </label>
        </div>

        <textarea
          rows={16}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          style={{ width: "100%", fontFamily: "monospace", padding: 12 }}
        />

        <div style={{ marginTop: 12 }}>
          <button onClick={handleSubmitInvoice} disabled={loadingSubmit} style={{ padding: "8px 12px" }}>
            {loadingSubmit ? "Submitting..." : "Submit Invoice"}
          </button>

          <button
            onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); setLastInvoiceId(null); }}
            style={{ marginLeft: 8, padding: "8px 12px" }}
          >
            Clear
          </button>

          <div style={{ marginTop: 10, color: statusMsg?.startsWith("Error") ? "#b91c1c" : "#065f46" }}>{statusMsg}</div>
        </div>
      </div>

      {/* RIGHT: Live Journey */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460, position: "sticky", top: 20 }}>
        {lastInvoiceId ? (
          <InvoiceJourney invoiceId={lastInvoiceId} />
        ) : (
          <div
            style={{
              border: "1px dashed #ccc",
              borderRadius: 8,
              padding: 24,
              color: "#777",
              textAlign: "center",
              marginTop: 60,
            }}
          >
            🧾 Generate and Submit an invoice to view its live journey here.
          </div>
        )}
      </div>
    </div>
  );
}
