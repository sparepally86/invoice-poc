// src/pages/Tasks.jsx
import React, { useEffect, useState } from "react";
import api from "../lib/api";

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actioning, setActioning] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api.getTasks();
      setTasks(Array.isArray(data) ? data : (data.items || []));
    } catch (e) {
      console.error(e);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleApprove(task) {
    if (!window.confirm("Approve this invoice?")) return;
    setActioning(task._id || task.id);
    try {
      await api.approveInvoice(task.invoice_id, { approver: "ui:user", comment: "approved via UI" });
      alert("Approved");
      await load();
    } catch (e) {
      console.error(e);
      alert("Approve failed: " + (e?.message || JSON.stringify(e)));
    } finally {
      setActioning(null);
    }
  }

  async function handleReject(task) {
    if (!window.confirm("Reject this invoice?")) return;
    setActioning(task._id || task.id);
    try {
      await api.rejectInvoice(task.invoice_id, { approver: "ui:user", comment: "rejected via UI" });
      alert("Rejected");
      await load();
    } catch (e) {
      console.error(e);
      alert("Reject failed: " + (e?.message || JSON.stringify(e)));
    } finally {
      setActioning(null);
    }
  }

  return (
    <div>
      <h1>Tasks (Human in the Loop)</h1>
      {loading ? <div>Loading…</div> : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>
              <th style={{ padding: 8 }}>Type</th>
              <th style={{ padding: 8 }}>Invoice ID</th>
              <th style={{ padding: 8 }}>Agent</th>
              <th style={{ padding: 8 }}>Created</th>
              <th style={{ padding: 8 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 && <tr><td colSpan={5}>No pending tasks</td></tr>}
            {tasks.map(t => (
              <tr key={t._id || t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: 8 }}>{t.type}</td>
                <td style={{ padding: 8 }}>{t.invoice_id}</td>
                <td style={{ padding: 8 }}>{t.payload?.agent || "-"}</td>
                <td style={{ padding: 8 }}>{t.created_at || "-"}</td>
                <td style={{ padding: 8 }}>
                  {t.type === "approval" ? (
                    <>
                      <button disabled={actioning} onClick={() => handleApprove(t)}>Approve</button>
                      <button disabled={actioning} onClick={() => handleReject(t)} style={{ marginLeft: 8 }}>Reject</button>
                    </>
                  ) : (
                    <>
                      <a href={`/invoices/${encodeURIComponent(t.invoice_id)}`}><button>Open</button></a>
                      <button onClick={() => alert("Edit inline JSON not yet implemented")} style={{ marginLeft: 8 }}>Edit</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
