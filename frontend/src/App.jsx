import React, { useState } from "react";
import axios from "axios";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "https://your-render-backend-url.onrender.com";

export default function App() {
  const [payload, setPayload] = useState(`{
  "source": {"capture_system":"CapturePOC", "capture_id":"cap-1001"},
  "buyer": {"buyer_id":"B001","name":"Example Buyer"},
  "vendor": {"vendor_id":"V0002","name_raw":"Indigo"},
  "header": {
    "invoice_number":{"value":"INV-2025-1001"},
    "invoice_date":{"value":"2025-10-01"},
    "grand_total":{"value":8500.00}
  },
  "lines":[]
}`);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState(null);

  const submit = async () => {
    setError(null);
    setResp(null);
    let json;
    try {
      json = JSON.parse(payload);
    } catch (e) {
      setError("Invalid JSON: " + e.message);
      return;
    }

    setLoading(true);
    try {
      const url = `${BACKEND_URL.replace(/\\/$/, "")}/api/v1/incoming`;
      const r = await axios.post(url, json, { timeout: 15000 });
      setResp(r.data);
    } catch (e) {
      if (e.response)
        setError(
          `Server error: ${e.response.status} ${JSON.stringify(e.response.data)}`
        );
      else setError("Network / CORS error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>Invoice POC — Paste Canonical JSON</h1>
      <p className="hint">
        Paste canonical invoice JSON and click Submit. Backend must expose{" "}
        <code>/api/v1/incoming</code>.
      </p>

      <textarea
        value={payload}
        onChange={(e) => setPayload(e.target.value)}
      ></textarea>

      <div className="controls">
        <button onClick={submit} disabled={loading}>
          {loading ? "Submitting..." : "Submit Invoice"}
        </button>
      </div>

      {error && <div className="error">Error: {error}</div>}

      {resp && (
        <div className="success">
          <h3>Response</h3>
          <pre>{JSON.stringify(resp, null, 2)}</pre>
          {resp.invoice_id && (
            <p>
              Invoice ID: <strong>{resp.invoice_id}</strong>
            </p>
          )}
        </div>
      )}

      <footer>
        <small>
          Backend URL: <code>{BACKEND_URL}</code>
        </small>
      </footer>
    </div>
  );
}
