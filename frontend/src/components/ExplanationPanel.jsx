// frontend/src/components/ExplanationPanel.jsx
import React, { useEffect, useState } from "react";

export default function ExplanationPanel({ invoiceId }) {
  const [loading, setLoading] = useState(false);
  const [explain, setExplain] = useState(null);
  const [error, setError] = useState(null);

  const fetchExplain = async () => {
    if (!invoiceId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/invoices/${encodeURIComponent(invoiceId)}/explain`);
      if (!res.ok) {
        const txt = await res.text();
        setError(`HTTP ${res.status}: ${txt}`);
        setLoading(false);
        return;
      }
      const data = await res.json();
      if (data && data.ok) {
        setExplain(data.explain);
      } else {
        setExplain(null);
      }
    } catch (e) {
      setError(String(e));
      setExplain(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExplain();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  if (!invoiceId) return null;

  return (
    <div style={{
      border: "1px solid #e5e7eb",
      padding: 12,
      borderRadius: 8,
      marginTop: 12,
      background: "#fafafa"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>AI Explanation</h3>
        <div>
          <button onClick={fetchExplain} disabled={loading} style={{ marginRight: 8 }}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && <div style={{ color: "crimson", marginTop: 8 }}>{error}</div>}

      {explain === null && !loading && (
        <div style={{ color: "#6b7280", marginTop: 8 }}>No explanation available yet.</div>
      )}

      {explain && (
        <div style={{ marginTop: 8 }}>
          <div style={{ marginBottom: 8, whiteSpace: "pre-wrap" }}>
            <strong>Explanation:</strong>
            <div style={{ marginTop: 6 }}>{explain.result && explain.result.explanation ? explain.result.explanation : String(explain)}</div>
          </div>

          {explain.result && explain.result.evidence && explain.result.evidence.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <strong>Evidence</strong>
              <ul>
                {explain.result.evidence.map((ev, idx) => (
                  <li key={idx}>{JSON.stringify(ev)}</li>
                ))}
              </ul>
            </div>
          )}

          {explain.result && explain.result.actions && explain.result.actions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <strong>Suggested actions</strong>
              <ul>
                {explain.result.actions.map((ac, idx) => (
                  <li key={idx}>{JSON.stringify(ac)}</li>
                ))}
              </ul>
            </div>
          )}

          {explain.ai && explain.ai.retrieval_hits && explain.ai.retrieval_hits.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <strong>Related cases</strong>
              <ul>
                {explain.ai.retrieval_hits.map((h, idx) => (
                  <li key={idx}>{h.id} (score: {h.score})</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ marginTop: 10, color: "#6b7280", fontSize: 12 }}>
            <div>Agent: {explain.agent}</div>
            <div>Score: {explain.score}</div>
            <div>Timestamp: {explain.timestamp}</div>
          </div>
        </div>
      )}
    </div>
  );
}
