// src/pages/Home.jsx
import React, { useEffect, useState } from "react";
import api from "../lib/api";

export default function Home() {
  const [stats, setStats] = useState({ invoices: 0, pending: 0, approved: 0, tasks: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const data = await api.getInvoices({ limit: 200 }).catch(() => ({ items: [] }));
        const tasks = await api.getTasks().catch(() => []);
        const invoices = Array.isArray(data) ? data : (data.items || []);
        let s = { invoices: invoices.length, pending: 0, approved: 0, tasks: Array.isArray(tasks) ? tasks.length : 0 };
        for (const inv of invoices) {
          if (inv.status === "PENDING_APPROVAL" || inv.status === "EXCEPTION") s.pending++;
          if (["APPROVED", "READY_FOR_POSTING", "POSTED"].includes(inv.status)) s.approved++;
        }
        if (!cancelled) setStats(s);
      } catch (err) {
        console.error("Home load error", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ padding: 16, borderRadius: 8, background: "#fff" }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Total Invoices</div>
          <div style={{ fontSize: 28 }}>{loading ? "…" : stats.invoices}</div>
        </div>
        <div style={{ padding: 16, borderRadius: 8, background: "#fff" }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Pending (HITL / Exceptions)</div>
          <div style={{ fontSize: 28 }}>{loading ? "…" : stats.pending}</div>
        </div>
        <div style={{ padding: 16, borderRadius: 8, background: "#fff" }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Approved / Posted</div>
          <div style={{ fontSize: 28 }}>{loading ? "…" : stats.approved}</div>
        </div>
        <div style={{ padding: 16, borderRadius: 8, background: "#fff" }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Open Tasks</div>
          <div style={{ fontSize: 28 }}>{loading ? "…" : stats.tasks}</div>
        </div>
      </div>

      <p style={{ marginTop: 18, color: "#6b7280", fontSize: 13 }}>
        Use the left navigation to access Invoices, Submit Invoice, and Tasks.
      </p>
    </div>
  );
}
