// src/pages/SubmitInvoice.jsx
import React, { useState } from "react";
import api from "../lib/api"; // if you have it; fallback to fetch inside
const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

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

  // checkboxes
  const [missMandatory, setMissMandatory] = useState(false);
  const [badVendor, setBadVendor] = useState(false);
  const [badPO, setBadPO] = useState(false);

  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      // call dev generator
      const params = new URLSearchParams();
      params.append("po_number", poNumber);
      if (splitFirstLine) params.append("split_first_line", "true");

      const url = `${BACKEND}/api/v1/dev/generate-invoice?${params.toString()}`;
      const resp = await fetch(url, { method: "POST" });
      const data = await resp.json();
      const generated = data?.generated_invoice || data;

      // mutate based on checkboxes
      const mutated = JSON.parse(JSON.stringify(generated)); // deep clone

      // a) remove mandatory field when requested
      if (missMandatory) {
        // drop invoice_ref if present
        if (mutated.header) {
          delete mutated.header.invoice_ref;
          // if there is invoice_number object, delete its value
          if (mutated.header.invoice_number && typeof mutated.header.invoice_number === "object") {
            delete mutated.header.invoice_number.value;
          }
        }
      }

      // b) bad vendor
      if (badVendor) {
        if (!mutated.header) mutated.header = {};
        mutated.header.vendor_number = "BAD-VENDOR-9999";
        mutated.header.vendor_name = "NonExistent Vendor";
        // also clear vendor section if present
        if (mutated.vendor) {
          mutated.vendor.vendor_id = "BAD-VENDOR-9999";
          mutated.vendor.name_raw = "NonExistent Vendor";
        }
      }

      // c) bad PO or mismatch
      if (badPO) {
        if (!mutated.header) mutated.header = {};
        mutated.header.po_number = "PO-BAD-000";
        // optionally change item amounts to mismatch PO totals
        if (mutated.items && mutated.items.length > 0) {
          // bump the first line amount slightly
          mutated.items[0].amount = (mutated.items[0].amount || 0) + 123.45;
        }
      }

      setJsonText(JSON.stringify(mutated, null, 2));
      setStatusMsg(`Generated invoice for ${poNumber} (mutated)`);
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
    try {
      // parse JSON and submit to incoming endpoint
      const json = JSON.parse(jsonText);
      const url = `${BACKEND}/api/v1/incoming`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(json),
      });
      const resp = await r.json();
      if (!r.ok) {
        setStatusMsg(`Submit error: ${JSON.stringify(resp)}`);
      } else {
        setStatusMsg(`Submitted — invoice_id: ${resp.invoice_id || JSON.stringify(resp)}`);
      }
    } catch (err) {
      console.error(err);
      setStatusMsg("Submit error: " + (err?.message || JSON.stringify(err)));
    } finally {
      setLoadingSubmit(false);
    }
  }

  return (
    <div>
      <h1>Submit Invoice (Capture simulation)</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
        <label>
          PO Number: <input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} style={{ marginLeft: 8 }} />
        </label>

        <label style={{ marginLeft: 12 }}>
          <input type="checkbox" checked={splitFirstLine} onChange={(e) => setSplitFirstLine(e.target.checked)} /> Split first line
        </label>

        <button onClick={handleGenerate} disabled={loadingGen} style={{ marginLeft: 8 }}>
          {loadingGen ? "Generating..." : "Generate"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
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
        <button onClick={handleSubmitInvoice} disabled={loadingSubmit}>{loadingSubmit ? "Submitting..." : "Submit Invoice"}</button>
        <button onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); }} style={{ marginLeft: 8 }}>Clear</button>
        <div style={{ marginTop: 8 }}>{statusMsg}</div>
      </div>
    </div>
  );
}
