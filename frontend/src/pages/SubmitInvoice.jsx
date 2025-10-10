// src/pages/SubmitInvoice.jsx
import React, { useState } from "react";
import api from "../lib/api";

export default function SubmitInvoice() {
  const [poNumber, setPoNumber] = useState("PO-1001");
  const [splitFirstLine, setSplitFirstLine] = useState(true);
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

  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      const resp = await api.generateInvoice(poNumber, splitFirstLine);
      const generated = resp?.generated_invoice || resp;
      setJsonText(JSON.stringify(generated, null, 2));
      setStatusMsg("Generated invoice");
    } catch (err) {
      console.error(err);
      setStatusMsg("Generation failed: " + (err?.message || JSON.stringify(err)));
    } finally {
      setLoadingGen(false);
    }
  }

  async function handleSubmit() {
    setStatusMsg(null);
    setLoadingSubmit(true);
    try {
      const payload = JSON.parse(jsonText);
      const resp = await api.postIncoming(payload);
      setStatusMsg("Submitted: " + JSON.stringify(resp));
    } catch (err) {
      console.error(err);
      setStatusMsg("Submit error: " + (err?.response?.data || err.message));
    } finally {
      setLoadingSubmit(false);
    }
  }

  return (
    <div>
      <h1>Submit Invoice (Capture simulation)</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <label>
          PO Number: <input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} style={{ marginLeft: 8 }} />
        </label>
        <label style={{ marginLeft: 12 }}>
          <input type="checkbox" checked={splitFirstLine} onChange={(e) => setSplitFirstLine(e.target.checked)} /> Split first line
        </label>
        <button onClick={handleGenerate} disabled={loadingGen}>{loadingGen ? "Generating..." : "Generate"}</button>
      </div>

      <textarea rows={16} value={jsonText} onChange={(e) => setJsonText(e.target.value)} style={{ width: "100%", fontFamily: "monospace", padding: 12 }} />

      <div style={{ marginTop: 12 }}>
        <button onClick={handleSubmit} disabled={loadingSubmit}>{loadingSubmit ? "Submitting..." : "Submit Invoice"}</button>
        <button onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); }} style={{ marginLeft: 8 }}>Clear</button>
        <div style={{ marginTop: 8 }}>{statusMsg}</div>
      </div>
    </div>
  );
}
