// src/pages/Home.jsx
import React, { useEffect, useState } from "react";
import api from "../lib/api";

export default function Home() {
  const [stats, setStats] = useState({ invoices: 0, pending: 0, approved: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        // get few invoices to compute quick stats (backend should support /invoices list)
        const data = await api.getInvoices({ limit: 200 });
        const tasks = await api.getTasks();
        if (cancelled) return;
        const invoices = Array.isArray(data) ? data : (data.items || []);
        let s = { invoices: invoices.length, pending: 0, approved: 0 };
        for (const inv of invoices) {
          if (inv.status === "PENDING_APPROVAL" || inv.status === "EXCEPTION") s.pending++;
          if (inv.status === "APPROVED" || inv.status === "POSTED") s.approved++;
        }
        // tasks length
        s.tasks = Array.isArray(tasks) ? tasks.length : (tasks.count || 0);
        setStats(s);
      } catch (e) {
        console.error(e);
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
        <div style={{ padding: 16, borderRadius: 8, background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
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

      <section style={{ marginTop: 24 }}>
        <h3>Quick actions</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <a href="/submit"><button>Submit Invoice (Capture simulation)</button></a>
          <a href="/invoices"><button>View Invoices</button></a>
          <a href="/tasks"><button>View Tasks</button></a>
        </div>
      </section>
    </div>
  );
}
