// src/pages/InvoiceDetail.jsx
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../lib/api";

/**
 * Invoice detail page
 * Route: /invoices/:id
 *
 * - GET invoice
 * - Display header, items, status
 * - Show workflow steps
 * - Approve / Reject buttons (calls api.approveInvoice / api.rejectInvoice)
 */

function PrettyBox({ title, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>{title}</div>
      <div style={{ background: "#fff", borderRadius: 8, padding: 12, border: "1px solid #e5e7eb" }}>{children}</div>
    </div>
  );
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState(false);
  const [msg, setMsg] = useState(null);

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
      // simple approver payload; you can pop a dialog to capture comment
      const resp = await api.approveInvoice(id, { approver: "ui:user", comment: "Approved via UI" });
      setMsg("Approved — " + JSON.stringify(resp));
      // refresh
      const doc = await api.getInvoice(id);
      setInvoice(doc);
    } catch (err) {
      console.error("approve error", err);
      setMsg("Approve failed: " + (err?.response?.data || err?.message));
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
      setMsg("Rejected — " + JSON.stringify(resp));
      // refresh
      const doc = await api.getInvoice(id);
      setInvoice(doc);
    } catch (err) {
      console.error("reject error", err);
      setMsg("Reject failed: " + (err?.response?.data || err?.message));
    } finally {
      setActioning(false);
    }
  }

  if (loading) return <div>Loading invoice...</div>;
  if (!invoice) return <div>Invoice not found. <button onClick={() => navigate("/invoices")}>Back to list</button></div>;

  const header = invoice.header || {};
  const items = invoice.items || invoice.lines || [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Invoice: {invoice._id || header.invoice_ref}</h1>

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => navigate("/invoices")} style={{ padding: "8px 12px" }}>Back</button>
          <button
            onClick={doApprove}
            disabled={actioning}
            style={{ padding: "8px 12px", background: "#10b981", color: "white", border: "none", borderRadius: 6 }}
          >
            {actioning ? "Working..." : "Approve"}
          </button>
          <button
            onClick={doReject}
            disabled={actioning}
            style={{ padding: "8px 12px", background: "#ef4444", color: "white", border: "none", borderRadius: 6 }}
          >
            {actioning ? "Working..." : "Reject"}
          </button>
        </div>
      </div>

      {msg && (
        <div style={{ marginTop: 8, marginBottom: 12, padding: 10, borderRadius: 6, background: "#fef3f2", color: "#7f1d1d" }}>
          {typeof msg === "string" ? msg : JSON.stringify(msg)}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
        <div>
          <PrettyBox title="Header">
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <tbody>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>Invoice Ref</td><td style={{ padding: 6 }}>{header.invoice_ref || invoice._id}</td></tr>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>Invoice Date</td><td style={{ padding: 6 }}>{header.invoice_date}</td></tr>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>Vendor</td><td style={{ padding: 6 }}>{header.vendor_name || (invoice.vendor && (invoice.vendor.name_raw || invoice.vendor.vendor_id)) || "-"}</td></tr>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>PO Number</td><td style={{ padding: 6 }}>{header.po_number || header.po || "-"}</td></tr>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>Currency / Amount</td><td style={{ padding: 6 }}>{header.currency || "-"} {header.amount ?? header.grand_total?.value ?? "-"}</td></tr>
                <tr><td style={{ padding: 6, color: "#6b7280" }}>Status</td><td style={{ padding: 6 }}>{invoice.status}</td></tr>
              </tbody>
            </table>
          </PrettyBox>

          <PrettyBox title="Line items">
            {items.length === 0 ? <div>No items</div> : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                    <th style={{ padding: 8 }}>#</th>
                    <th style={{ padding: 8 }}>Description</th>
                    <th style={{ padding: 8 }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #f6f6f6" }}>
                      <td style={{ padding: 8 }}>{idx + 1}</td>
                      <td style={{ padding: 8 }}>{it.item_text || it.description || it.name || "-"}</td>
                      <td style={{ padding: 8 }}>{it.amount ?? it.total ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </PrettyBox>

          <PrettyBox title="Full document (JSON)">
            <pre style={{ whiteSpace: "pre-wrap", maxHeight: 280, overflow: "auto", background: "#f8fafc", padding: 8 }}>
              {JSON.stringify(invoice, null, 2)}
            </pre>
          </PrettyBox>
        </div>

        <div>
          <PrettyBox title="Workflow / Journey (last steps)">
            {Array.isArray(invoice._workflow?.steps) && invoice._workflow.steps.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {invoice._workflow.steps.slice().reverse().map((s, i) => (
                  <div key={i} style={{ padding: 10, borderRadius: 8, background: "#fff", border: "1px solid #eee" }}>
                    <div style={{ fontSize: 13, color: "#111827", marginBottom: 6 }}>
                      <strong>{s.agent || s.type || "step"}</strong>
                      <span style={{ color: "#6b7280", marginLeft: 8 }}>{s.status || s.type || ""}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>{s.timestamp || s.ts || s.created_at}</div>
                    <div style={{ marginTop: 8 }}>
                      <pre style={{ whiteSpace: "pre-wrap", maxHeight: 160, overflow: "auto", background: "#f8fafc", padding: 8 }}>
                        {JSON.stringify(s.result || s, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div>No workflow steps recorded.</div>
            )}
          </PrettyBox>
        </div>
      </div>
    </div>
  );
}
