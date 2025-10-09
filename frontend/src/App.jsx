// frontend/src/App.jsx
import React from "react";
import { useState } from "react";
import axios from "axios";

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function App() {
  const [poNumber, setPoNumber] = useState("PO-1001");
  const [splitFirstLine, setSplitFirstLine] = useState(true);
  const [jsonText, setJsonText] = useState(`{
  "header": {
    "erpsystem": "ecc",
    "source": "capture",
    "buyer_companycode": "1000",
    "invoice_ref": "TEST23127",
    "invoice_date": "2025-09-11",
    "vendor_number": "1000",
    "vendor_name": "C.E.B. NEW YORK",
    "currency": "USD",
    "amount": 1000,
    "status": 2
  },
  "items": []
}`);
  const [statusMsg, setStatusMsg] = useState(null);
  const [loadingGen, setLoadingGen] = useState(false);
  const [loadingSubmit, setLoadingSubmit] = useState(false);
  const [backendUrlShown] = useState(BACKEND_URL);

  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      // call dev generator
      const params = new URLSearchParams();
      params.append("po_number", poNumber);
      if (splitFirstLine) params.append("split_first_line", "true");

      const url = `${BACKEND_URL}/api/v1/dev/generate-invoice?${params.toString()}`;
      const resp = await axios.post(url, null, { timeout: 15000 });
      const generated = resp.data?.generated_invoice;
      if (!generated) {
        setStatusMsg("No invoice returned from generator.");
      } else {
        // Pretty print and set into textarea for editing
        setJsonText(JSON.stringify(generated, null, 2));
        setStatusMsg(`Generated invoice for ${poNumber}`);
      }
    } catch (err) {
      console.error(err);
      const msg = err?.response?.data?.detail || err.message || "Generation failed";
      setStatusMsg(`Error: ${msg}`);
    } finally {
      setLoadingGen(false);
    }
  }

  async function handleSubmitInvoice() {
    setStatusMsg(null);
    setLoadingSubmit(true);
    try {
      // parse JSON and submit to incoming endpoint
      const json = JSON.parse(jsonText);
      const url = `${BACKEND_URL}/api/v1/incoming`;
      const r = await axios.post(url, json, { timeout: 15000 });
      setStatusMsg(`Submitted — invoice_id: ${r.data?.invoice_id || JSON.stringify(r.data)}`);
    } catch (err) {
      console.error(err);
      if (err instanceof SyntaxError) {
        setStatusMsg("Invalid JSON in textarea. Fix it and try again.");
      } else {
        const msg = err?.response?.data || err.message;
        setStatusMsg(`Submit error: ${JSON.stringify(msg)}`);
      }
    } finally {
      setLoadingSubmit(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "28px auto", fontFamily: "Inter, system-ui, sans-serif" }}>
      <h1>Invoice POC — Paste or Generate Invoice JSON</h1>

      <div style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "center" }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          PO Number:
          <input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} style={{ padding: "6px 10px" }} />
        </label>

        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={splitFirstLine} onChange={(e) => setSplitFirstLine(e.target.checked)} />
          Split first line (1000/2000)
        </label>

        <button onClick={handleGenerate} disabled={loadingGen} style={{ padding: "8px 12px", background: "#10b981", color: "white", border: "none", borderRadius: 6 }}>
          {loadingGen ? "Generating..." : "Generate Invoice"}
        </button>

        <div style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>
          Backend URL: <span style={{ background: "#f3f4f6", padding: "4px 8px", borderRadius: 6 }}>{backendUrlShown}</span>
        </div>
      </div>

      <textarea
        rows={18}
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        style={{ width: "100%", padding: 14, borderRadius: 8, border: "1px solid #e5e7eb", fontFamily: "monospace", fontSize: 13 }}
      />

      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <button onClick={handleSubmitInvoice} disabled={loadingSubmit} style={{ padding: "10px 14px", background: "#047857", color: "white", border: "none", borderRadius: 6 }}>
          {loadingSubmit ? "Submitting..." : "Submit Invoice"}
        </button>

        <button onClick={() => { setJsonText("{}"); setStatusMsg("Cleared textarea"); }} style={{ padding: "10px 14px" }}>
          Clear
        </button>

        <div style={{ marginLeft: "auto", color: statusMsg && statusMsg.startsWith("Error") ? "#b91c1c" : "#065f46" }}>
          {statusMsg}
        </div>
      </div>

      <p style={{ marginTop: 18, color: "#6b7280", fontSize: 13 }}>
        Tip: edit the generated JSON before Submit to test validation / exceptions.
      </p>
    </div>
  );
}
