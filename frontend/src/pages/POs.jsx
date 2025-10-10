// src/pages/POs.jsx
import React, { useEffect, useState } from "react";
const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

function Chevron({ open }) {
  return <span style={{ display: "inline-block", transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "0.12s" }}>▶</span>;
}

export default function POs() {
  const [pos, setPos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openMap, setOpenMap] = useState({});
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const resp = await fetch(`${BACKEND}/api/v1/pos`);
        const data = await resp.json();
        const items = Array.isArray(data) ? data : data.items || [];
        if (!cancelled) setPos(items);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  function toggle(poNumber) {
    setOpenMap((m) => ({ ...m, [poNumber]: !m[poNumber] }));
  }

  return (
    <div>
      <h1>PO Master</h1>
      {loading && <div>Loading POs…</div>}
      {err && <div style={{ color: "red" }}>Error: {err}</div>}
      {!loading && pos.length === 0 && <div>No POs found.</div>}

      {pos.length > 0 && (
        <div style={{ display: "grid", gap: 12 }}>
          {pos.map((p, idx) => {
            const poNumber = p.po_number || p._id || p.number || `PO-${idx+1}`;
            const open = !!openMap[poNumber];
            const lines = p.lines || p.items || [];
            return (
              <div key={idx} style={{ border: "1px solid #e6e6e6", borderRadius: 8, padding: 12, background: "#fff" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <button onClick={() => toggle(poNumber)} style={{ marginRight: 10, background: "transparent", border: "none", cursor: "pointer" }}>
                      <Chevron open={open} />
                    </button>
                    <strong>{poNumber}</strong>
                    <div style={{ fontSize: 13, color: "#6b7280" }}>Supplier: {p.vendor_name || p.vendor || "-"}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 13, color: "#6b7280" }}>Total: {p.total || p.amount || "-"}</div>
                    <div style={{ fontSize: 12, color: "#9ca3af" }}>{p.status || ""}</div>
                  </div>
                </div>

                {open && (
                  <div style={{ marginTop: 12 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                          <th style={{ padding: 8 }}>#</th>
                          <th style={{ padding: 8 }}>Description</th>
                          <th style={{ padding: 8 }}>Qty</th>
                          <th style={{ padding: 8 }}>Unit Price</th>
                          <th style={{ padding: 8 }}>Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lines.map((ln, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid #f6f6f6" }}>
                            <td style={{ padding: 8 }}>{i + 1}</td>
                            <td style={{ padding: 8 }}>{ln.item_text || ln.description || ln.name || "-"}</td>
                            <td style={{ padding: 8 }}>{ln.qty ?? ln.quantity ?? "-"}</td>
                            <td style={{ padding: 8 }}>{ln.unit_price ?? ln.price ?? "-"}</td>
                            <td style={{ padding: 8 }}>{ln.amount ?? ln.line_total ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
