  return (
    <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
      {/* LEFT: Generate + Submit panel */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460 }}>
        <h1>Submit Invoice (Capture simulation)</h1>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", marginBottom: 12 }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="radio" name="mode" value="po" checked={mode === "po"} onChange={() => setMode("po")} />
            PO-based (backend chooses random PO if none specified)
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="radio" name="mode" value="nonpo" checked={mode === "nonpo"} onChange={() => setMode("nonpo")} />
            Non-PO based
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: 12 }}>
            <input type="checkbox" checked={splitLineItem} onChange={(e) => setSplitLineItem(e.target.checked)} />
            Split line item
          </label>

          <button onClick={handleGenerate} disabled={loadingGen} style={{ marginLeft: "auto" }}>
            {loadingGen ? "Generating..." : "Generate"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 18, marginBottom: 12 }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={missMandatory} onChange={(e) => setMissMandatory(e.target.checked)} />
            Miss mandatory field
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={badVendor} onChange={(e) => setBadVendor(e.target.checked)} />
            Bad / missing vendor
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={badPO} onChange={(e) => setBadPO(e.target.checked)} />
            Bad / mismatched PO
          </label>
        </div>

        <textarea
          rows={16}
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          style={{ width: "100%", fontFamily: "monospace", padding: 12 }}
        />

        <div style={{ marginTop: 12 }}>
          <button onClick={handleSubmitInvoice} disabled={loadingSubmit} style={{ padding: "8px 12px" }}>
            {loadingSubmit ? "Submitting..." : "Submit Invoice"}
          </button>

          <button
            onClick={() => { setJsonText("{}"); setStatusMsg("Cleared"); setLastInvoiceId(null); }}
            style={{ marginLeft: 8, padding: "8px 12px" }}
          >
            Clear
          </button>

          <div style={{ marginTop: 10, color: statusMsg?.startsWith("Error") ? "#b91c1c" : "#065f46" }}>{statusMsg}</div>
        </div>
      </div>

      {/* RIGHT: Live Journey */}
      <div style={{ flex: 1, maxWidth: "50%", minWidth: 460, position: "sticky", top: 20 }}>
        {lastInvoiceId ? (
          <InvoiceJourney invoiceId={lastInvoiceId} />
        ) : (
          <div
            style={{
              border: "1px dashed #ccc",
              borderRadius: 8,
              padding: 24,
              color: "#777",
              textAlign: "center",
              marginTop: 60,
            }}
          >
            🧾 Generate and Submit an invoice to view its live journey here.
          </div>
        )}
      </div>
    </div>
  );
