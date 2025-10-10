// src/pages/Vendors.jsx
import React, { useEffect, useState } from "react";
const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function Vendors() {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const resp = await fetch(`${BACKEND}/api/v1/vendors`);
        const data = await resp.json();
        const items = Array.isArray(data) ? data : data.items || [];
        if (!cancelled) setVendors(items);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  return (
    <div>
      <h1>Vendor Master</h1>
      {loading && <div>Loading vendors…</div>}
      {err && <div style={{ color: "red" }}>Error: {err}</div>}
      {!loading && vendors.length === 0 && <div>No vendors found.</div>}

      {vendors.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e6e6e6" }}>
              <th style={{ padding: 8 }}>Vendor ID</th>
              <th style={{ padding: 8 }}>Name</th>
              <th style={{ padding: 8 }}>Country / Notes</th>
            </tr>
          </thead>
          <tbody>
            {vendors.map((v, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                <td style={{ padding: 8 }}>{v.vendor_id || v._id || v.vendorId || "-"}</td>
                <td style={{ padding: 8 }}>{v.name_raw || v.name || v.vendor_name || "-"}</td>
                <td style={{ padding: 8 }}>{v.country || v.notes || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
