// src/App.jsx
import React from "react";
import { Outlet, NavLink } from "react-router-dom";

const NavItem = ({ to, children }) => (
  <div style={{ margin: "8px 0" }}>
    <NavLink
      to={to}
      style={({ isActive }) => ({
        color: isActive ? "#111827" : "#6b7280",
        textDecoration: "none",
        fontWeight: isActive ? 700 : 400,
      })}
    >
      {children}
    </NavLink>
  </div>
);

export default function App() {
  const backend = import.meta.env.VITE_BACKEND_URL || "env not set";
  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "Inter, system-ui, sans-serif" }}>
      <nav style={{ width: 220, padding: 20, borderRight: "1px solid #e5e7eb" }}>
        <h2 style={{ marginTop: 0 }}>Invoice POC</h2>
        <NavItem to="/">Home</NavItem>
        <NavItem to="/invoices">Invoices</NavItem>
        <NavItem to="/submit">Submit Invoice</NavItem>
        <NavItem to="/tasks">Tasks (HITL)</NavItem>

        <div style={{ marginTop: 30, color: "#6b7280", fontSize: 12 }}>
          Backend: <br />
          <code style={{ wordBreak: "break-all" }}>{backend}</code>
        </div>
      </nav>

      <main style={{ flex: 1, padding: 20 }}>
        <Outlet />
      </main>
    </div>
  );
}
