// src/App.jsx
import React from "react";
import { Outlet, Link } from "react-router-dom";

export default function App() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "Inter, system-ui, sans-serif" }}>
      <nav style={{ width: 220, padding: 20, borderRight: "1px solid #e5e7eb" }}>
        <h2 style={{ marginTop: 0 }}>Invoice POC</h2>
        <ul style={{ listStyle: "none", padding: 0 }}>
          <li style={{ margin: "8px 0" }}><Link to="/">Home</Link></li>
          <li style={{ margin: "8px 0" }}><Link to="/invoices">Invoices</Link></li>
          <li style={{ margin: "8px 0" }}><Link to="/submit">Submit Invoice</Link></li>
          <li style={{ margin: "8px 0" }}><Link to="/tasks">Tasks (HITL)</Link></li>
        </ul>
        <div style={{ marginTop: 30, color: "#6b7280", fontSize: 12 }}>
          Backend: <br />
          <code style={{ wordBreak: "break-all" }}>{(import.meta.env.VITE_BACKEND_URL || "env not set")}</code>
        </div>
      </nav>

      <main style={{ flex: 1, padding: 20 }}>
        <Outlet />
      </main>
    </div>
  );
}
