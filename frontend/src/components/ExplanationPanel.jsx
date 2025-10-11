// frontend/src/components/ExplanationPanel.jsx
import React, { useEffect, useState } from "react";

export default function ExplanationPanel({ invoiceId }) {
  const [loading, setLoading] = useState(false);
  const [explain, setExplain] = useState(null);
  const [error, setError] = useState(null);
  const [feedbackList, setFeedbackList] = useState([]);
  const [sending, setSending] = useState(false);
  const [editNotes, setEditNotes] = useState("");

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

  const fetchFeedback = async () => {
    if (!invoiceId) return;
    try {
      const res = await fetch(`/api/v1/invoices/${encodeURIComponent(invoiceId)}/feedback`);
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.ok) setFeedbackList(data.feedback || []);
    } catch (e) {
      // ignore fetch feedback errors; UI still works
    }
  };

  useEffect(() => {
    fetchExplain();
    fetchFeedback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  const postFeedback = async (verdict, notes = "") => {
    if (!invoiceId) return;
    setSending(true);
    try {
      const payload = {
        invoice_id: invoiceId,
        step_id: explain && explain.timestamp ? explain.timestamp : null,
        verdict,
        notes,
        user: "ui:user" // TODO: replace with real user id from auth
      };
      const res = await fetch(`/api/v1/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const txt = await res.text();
        setError(`Feedback submit failed: ${res.status} ${txt}`);
      } else {
        // refresh feedback list and explain (if needed)
        await fetchFeedback();
        // optimistic UI: if accepted, optionally hide buttons or show accepted state
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  };

  const onAccept = async () => {
    if (!confirm("Mark this explanation as ACCEPTED?")) return;
    await postFeedback("accept", "");
    // optionally show a quick success message
  };

  const onReject = async () => {
    if (!confirm("Mark this explanation as REJECTED?")) return;
    await postFeedback("reject", "");
  };

  const onSuggestEdit = async () => {
    const notes = editNotes && editNotes.trim();
    if (!notes) {
      alert("Please provide suggested edit notes before sending.");
      return;
    }
    await postFeedback("suggest_edit", notes);
    setEditNotes("");
  };

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
          <button onClick={() => { fetchExplain(); fetchFeedback(); }} disabled={loading} style={{ marginRight: 8 }}>
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

          {/* Feedback controls */}
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button onClick={onAccept} disabled={sending} style={{ padding: "6px 10px", background: "#10b981", color: "#fff", border: "none", borderRadius: 6 }}>
              Accept
            </button>
            <button onClick={onReject} disabled={sending} style={{ padding: "6px 10px", background: "#ef4444", color: "#fff", border: "none", borderRadius: 6 }}>
              Reject
            </button>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                placeholder="Suggested edit (notes)"
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                style={{ padding: 6, minWidth: 220, borderRadius: 6, border: "1px solid #e5e7eb" }}
              />
              <button onClick={onSuggestEdit} disabled={sending} style={{ padding: "6px 10px", borderRadius: 6 }}>Suggest edit</button>
            </div>
          </div>

          {/* Feedback list */}
          <div style={{ marginTop: 12 }}>
            <strong>Recent feedback</strong>
            {feedbackList.length === 0 ? (
              <div style={{ color: "#6b7280", marginTop: 6 }}>No feedback yet.</div>
            ) : (
              <ul style={{ marginTop: 6 }}>
                {feedbackList.map((f) => (
                  <li key={f._id} style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 13 }}><strong>{f.verdict}</strong> — <span style={{ color: "#6b7280" }}>{f.user}</span></div>
                    <div style={{ fontSize: 12, color: "#374151" }}>{f.notes}</div>
                    <div style={{ fontSize: 11, color: "#6b7280" }}>{f.created_at}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
