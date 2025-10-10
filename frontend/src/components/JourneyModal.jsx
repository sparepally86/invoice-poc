// src/components/JourneyModal.jsx
import React from "react";

export default function JourneyModal({ open, onClose, steps }) {
  if (!open) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.4)", zIndex: 1000
    }}>
      <div style={{ width: "90%", maxHeight: "85vh", overflow: "auto", background: "#fff", padding: 20, borderRadius: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Invoice Journey</h3>
          <button onClick={onClose}>Close</button>
        </div>
        <ol>
          {Array.isArray(steps) && steps.map((s, i) => (
            <li key={i} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: "#374151" }}>
                <strong>{s.agent || s.type || "step"}</strong> — <span style={{ color: "#6b7280" }}>{s.status || s.type || ""}</span>
                <div style={{ fontSize: 12, color: "#6b7280" }}>{s.timestamp || s.ts}</div>
              </div>
              <pre style={{ background: "#f8fafc", padding: 8, borderRadius: 6, fontSize: 12, overflow: "auto" }}>
                {JSON.stringify(s.result || s, null, 2)}
              </pre>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
