// frontend/src/App.jsx
import React, { useState } from "react";
import axios from "axios";

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function App() {
  // Invoice UI state
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

  // Tasks UI state
  const [showTasks, setShowTasks] = useState(false);
  const [tasksList, setTasksList] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  // ---------- Invoice generator & submit ----------
  async function handleGenerate() {
    setStatusMsg(null);
    setLoadingGen(true);
    try {
      const params = new URLSearchParams();
      params.append("po_number", poNumber);
      if (splitFirstLine) params.append("split_first_line", "true");

      const url = `${BACKEND_URL}/api/v1/dev/generate-invoice?${params.toString()}`;
      const resp = await axios.post(url, null, { timeout: 15000 });
      const generated = resp.data?.generated_invoice;
      if (!generated) {
        setStatusMsg("No invoice returned from generator.");
      } else {
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

  // ---------- Tasks: load, approve ----------
  async function loadTasks() {
    setLoadingTasks(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/v1/tasks/pending`, { timeout: 10000 });
      setTasksList(r.data || []);
    } catch (e) {
      console.error("failed to load tasks", e);
      setTasksList([]);
    } finally {
      setLoadingTasks(false);
    }
  }

  async function approveTask(tid) {
    try {
      await axios.post(`${BACKEND_URL}/api/v1/tasks/${tid}/action`, { action: "approve" }, { timeout: 10000 });
      // reload tasks after action
      await loadTasks();
      setStatusMsg("Task approved");
    } catch (e) {
      console.error("approve failed", e);
      setStatusMsg(`Approve failed: ${e?.response?.data || e.message}`);
    }
  }

  // Optional: function to open tasks and load them
  function openTasks() {
    setShowTasks(true);
    loadTasks();
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

        <div style={{ marginLeft: "auto", fontSize: 12, color: "#666", display: "flex", gap: 8, alignItems: "center" }}>
          <span>Backend URL:</span>
          <span style={{ background: "#f3f4f6", padding: "4px 8px", borderRadius: 6 }}>{backendUrlShown}</span>
          <button onClick={openTasks} style={{ padding: "6px 10px", background: "#0ea5a4", color: "white", border: "none", borderRadius: 6 }}>
            Tasks
          </button>
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

      {/* Tasks drawer/modal */}
      {showTasks && (
        <div style={{ position: "fixed", right: 20, top: 60, width: 520, maxHeight: "75vh", overflow: "auto", background: "white", boxShadow: "0 8px 24px rgba(0,0,0,0.15)", padding: 16, borderRadius: 8, zIndex: 9999 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Pending Tasks</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={loadTasks} style={{ padding: "6px 10px" }}>Reload</button>
              <button onClick={() => setShowTasks(false)} style={{ padding: "6px 10px" }}>Close</button>
            </div>
          </div>

          {loadingTasks ? (
            <div>Loading...</div>
          ) : (
            <div>
              {tasksList.length === 0 && <div style={{ color: "#6b7280" }}>No pending tasks</div>}
              {tasksList.map(t => (
                <div key={t._id} style={{ padding: 10, borderBottom: "1px solid #eee", marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div><strong>{t.type}</strong> — invoice: <code>{t.invoice_id}</code></div>
                      <div style={{ fontSize: 12, color: "#666" }}>{t.payload?.reason}</div>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button onClick={() => approveTask(t._id)} style={{ background: "#059669", color: "white", padding: "6px 8px", border: "none", borderRadius: 6 }}>Approve</button>
                    </div>
                  </div>

                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: "#444", marginBottom: 6 }}>Agent result / evidence:</div>
                    <pre style={{ fontSize: 12, background: "#fafafa", padding: 8, whiteSpace: "pre-wrap" }}>{JSON.stringify(t.payload?.agent_result, null, 2)}</pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
