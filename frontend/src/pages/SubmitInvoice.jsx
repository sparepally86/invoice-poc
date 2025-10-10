// frontend/src/pages/SubmitInvoice.jsx
import React, { useState } from "react";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function SubmitInvoice() {
  // mode: "po" or "nonpo"
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

  // mutation checkboxes
  const [missMandatory, setMissMandatory] = useState(false);
  const [badVendor, setBadVendor] = useState(false);
  const [badPO, setBadPO] = useState(false);

  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      // Build generator endpoint.
      const params = new URLSearchParams();
      params.append("mode", mode); // tell backend whether we want PO or non-PO behavior
      if (splitLineItem) params.append("split_first_line", "true");

      const url = `${BACKEND}/api/v1/dev/generate-invoice?${params.toString()}`;
      const resp = await fetch(url, { method: "POST" });

      // read response body even on error to show message
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setStatusMsg(`Generator error: ${JSON.stringify(data)}`);
        setLoadingGen(false);
        return;
      }

      const generated = data?.generated_invoice || data || {};
      const mutated = JSON.parse(JSON.stringify(generated));

      // a) remove mandatory field when requested
      if (missMandatory) {
        if (mutated.header) {
          delete mutated.header.invoice_ref;
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
        if (mutated.vendor) {
          mutated.vendor.vendor_id = "BAD-VENDOR-9999";
          mutated.vendor.name_raw = "NonExistent Vendor";
        }
      }

      // c) bad PO or mismatch
      if (badPO) {
        if (!mutated.header) mutated.header = {};
        mutated.header.po_number = "PO-BAD-000";
        if (mutated.items && mutated.items.length > 0) {
          mutated.items[0].amount = (mutated.items[0].amount || 0) + 123.45;
        }
      }

      setJsonText(JSON.stringify(mutated, null, 2));
      setStatusMsg(`Generated invoice (${mode === "po" ? "PO-based (random/selected)" : "Non-PO"})`);
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
    <div style={{ maxWidth: 1000 }}>
      <h1>Submit Invoice (Capture simulation)</h1>

      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12 }}>
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
        <button onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); }} style={{ marginLeft: 8, padding: "8px 12px" }}>
          Clear
        </button>
        <div style={{ marginTop: 10 }}>{statusMsg}</div>
      </div>
    </div>
  );
}
