// src/pages/Invoices.jsx
import React, { useEffect, useState } from "react";
import api from "../lib/api";
import JourneyModal from "../components/JourneyModal";
import { Link, useNavigate } from "react-router-dom";

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedSteps, setSelectedSteps] = useState(null);

  async function load(qstr = "") {
    setLoading(true);
    try {
      // backend may not support search param 'q'; we pass as query and handle server side if implemented
      const data = await api.getInvoices({ q: qstr, limit: 200 });
      // if server returns object with items, handle it
      const items = Array.isArray(data) ? data : (data.items || data.invoices || []);
      setInvoices(items);
    } catch (e) {
      console.error(e);
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const onSearch = async () => { await load(q); };

  return (
    <div>
      <h1>Invoices</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search invoice_ref or PO number" style={{ padding: 8, flex: 1 }} />
        <button onClick={onSearch}>Search</button>
        <button onClick={() => load("")}>Clear</button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", background: "#fff" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>
            <th style={{ padding: 8 }}>Invoice Ref</th>
            <th style={{ padding: 8 }}>Vendor</th>
            <th style={{ padding: 8 }}>PO</th>
            <th style={{ padding: 8 }}>Amount</th>
            <th style={{ padding: 8 }}>Status</th>
            <th style={{ padding: 8 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={6}>Loading…</td></tr>
          ) : invoices.length === 0 ? (
            <tr><td colSpan={6}>No invoices</td></tr>
          ) : invoices.map(inv => (
            <tr key={inv._id || inv.header?.invoice_ref} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: 8 }}>{inv.header?.invoice_ref || inv._id}</td>
              <td style={{ padding: 8 }}>{inv.vendor?.name_raw || inv.header?.vendor_name || "-"}</td>
              <td style={{ padding: 8 }}>{inv.header?.po_number || inv.header?.po || "-"}</td>
              <td style={{ padding: 8 }}>{inv.header?.grand_total?.value ?? inv.header?.amount ?? "-"}</td>
              <td style={{ padding: 8 }}>{inv.status}</td>
              <td style={{ padding: 8 }}>
                <button onClick={() => setSelectedSteps(inv._workflow?.steps || [])}>Journey</button>
                <Link
                    to={`/invoices/${inv._id || inv.header?.invoice_ref}`}
                    style={{
                    padding: "6px 10px",
                    border: "1px solid #d1d5db",
                    borderRadius: 6,
                    background: "#f9fafb",
                    textDecoration: "none",
                    color: "#111827",
                    marginRight: 8,
                    }}
                >
                    Open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <JourneyModal open={!!selectedSteps} onClose={() => setSelectedSteps(null)} steps={selectedSteps || []} />
    </div>
  );
}
