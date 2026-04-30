import React, { useState, useEffect } from "react";

interface Database {
  id: number;
  name: string;
}

const VIZ_LABELS: Record<string, string> = {
  echarts_timeseries_line: "Line Chart",
  echarts_timeseries_bar: "Bar Chart",
  echarts_bar: "Bar Chart",
  pie: "Pie Chart",
  table: "Table",
  big_number_total: "Big Number",
};

function readSqlFromEditor(): string {
  try {
    const ace = (window as any).ace;
    if (ace) {
      const editors = document.querySelectorAll(".ace_editor");
      if (editors.length > 0) {
        return ace.edit(editors[editors.length - 1] as HTMLElement).getValue();
      }
    }
  } catch (_) {}
  return "";
}

export function ChartGenPanel() {
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [sql, setSql] = useState("");
  const [intent, setIntent] = useState("");
  const [suggestion, setSuggestion] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [createdUrl, setCreatedUrl] = useState("");

  useEffect(() => {
    fetch("/api/v1/database/", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((data) => {
        const dbs: Database[] = (data.result || [])
          .filter((d: any) => d.backend !== "sqlite" && d.database_name !== "SQLite")
          .map((d: any) => ({ id: d.id, name: d.database_name }));
        setDatabases(dbs);
        if (dbs.length > 0) setSelectedDbId(dbs[0].id);
      })
      .catch(() => {});

    const fromEditor = readSqlFromEditor();
    if (fromEditor.trim()) setSql(fromEditor);
  }, []);

  function handleLoadFromEditor() {
    const s = readSqlFromEditor();
    if (s.trim()) {
      setSql(s);
      setSuggestion(null);
      setError("");
      setCreatedUrl("");
    }
  }

  async function handleSuggest() {
    if (!sql.trim()) {
      setError("Enter SQL or load from the editor first.");
      return;
    }
    setLoading(true);
    setError("");
    setSuggestion(null);
    setCreatedUrl("");

    try {
      const response = await fetch("/api/v1/bi-ai/chartgen/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ sql, columns: [], question: intent }),
      });
      if (response.status === 401) {
        setError("Not authenticated. Please log in to Superset.");
        return;
      }
      const result = await response.json();
      if (result.status === "success") {
        setSuggestion(result);
      } else {
        setError(result.explanation || "Could not suggest a chart.");
      }
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!suggestion || !selectedDbId) return;
    setCreating(true);
    setError("");

    try {
      const response = await fetch("/api/v1/bi-ai/chartgen/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ sql, database_id: selectedDbId, suggestion }),
      });
      const result = await response.json();
      if (result.explore_url) {
        setCreatedUrl(result.explore_url);
        window.open(result.explore_url, "_blank");
      } else {
        setError(result.error || "Could not create chart.");
      }
    } catch {
      setError("Network error.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div
      style={{
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        boxSizing: "border-box",
      }}
    >
      {/* Database */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <label style={{ fontSize: "12px", color: "#666" }}>Database</label>
        <select
          value={selectedDbId ?? ""}
          onChange={(e) => setSelectedDbId(Number(e.target.value))}
          style={{
            padding: "6px 8px",
            border: "1px solid #d9d9d9",
            borderRadius: "4px",
            fontSize: "13px",
          }}
        >
          {databases.length === 0 && <option value="">Loading…</option>}
          {databases.map((db) => (
            <option key={db.id} value={db.id}>
              {db.name}
            </option>
          ))}
        </select>
      </div>

      {/* SQL */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label style={{ fontSize: "12px", color: "#666" }}>SQL</label>
          <button
            onClick={handleLoadFromEditor}
            style={{
              background: "none",
              border: "1px solid #d9d9d9",
              borderRadius: "4px",
              padding: "2px 8px",
              cursor: "pointer",
              fontSize: "11px",
              color: "#666",
            }}
          >
            Load from editor
          </button>
        </div>
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="Paste SQL or click 'Load from editor'…"
          rows={5}
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "8px",
            border: "1px solid #d9d9d9",
            borderRadius: "4px",
            fontSize: "12px",
            resize: "vertical",
            fontFamily: "monospace",
          }}
        />
      </div>

      {/* Optional intent */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <label style={{ fontSize: "12px", color: "#666" }}>
          What do you want to see? <span style={{ color: "#bbb" }}>(optional)</span>
        </label>
        <input
          type="text"
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="e.g. trend over time, comparison by line…"
          style={{
            padding: "6px 8px",
            border: "1px solid #d9d9d9",
            borderRadius: "4px",
            fontSize: "13px",
          }}
        />
      </div>

      <button
        onClick={handleSuggest}
        disabled={loading || !sql.trim()}
        style={{
          background: loading || !sql.trim() ? "#ccc" : "#722ed1",
          color: "white",
          border: "none",
          borderRadius: "4px",
          padding: "8px 16px",
          cursor: loading || !sql.trim() ? "not-allowed" : "pointer",
          fontSize: "13px",
          fontWeight: 600,
        }}
      >
        {loading ? "Analyzing…" : "Suggest Chart"}
      </button>

      {error && (
        <div
          style={{
            background: "#fff2f0",
            border: "1px solid #ffccc7",
            borderRadius: "4px",
            padding: "8px",
            fontSize: "12px",
            color: "#cf1322",
          }}
        >
          {error}
        </div>
      )}

      {suggestion && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {/* Chart type badge */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                background: "#f9f0ff",
                border: "1px solid #d3adf7",
                borderRadius: "4px",
                padding: "2px 10px",
                fontSize: "12px",
                color: "#722ed1",
                fontWeight: 600,
              }}
            >
              {VIZ_LABELS[suggestion.viz_type] ?? suggestion.viz_type}
            </span>
            <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
              {suggestion.title}
            </span>
          </div>

          {suggestion.explanation && (
            <div
              style={{
                background: "#f6ffed",
                border: "1px solid #b7eb8f",
                borderRadius: "4px",
                padding: "8px",
                fontSize: "12px",
                color: "#389e0d",
              }}
            >
              {suggestion.explanation}
            </div>
          )}

          {/* Config summary */}
          <div
            style={{
              background: "#fafafa",
              border: "1px solid #f0f0f0",
              borderRadius: "4px",
              padding: "8px",
              fontSize: "11px",
              color: "#666",
              lineHeight: 1.6,
            }}
          >
            {suggestion.x_axis && (
              <div>
                <strong>X-axis:</strong> {suggestion.x_axis}
              </div>
            )}
            {suggestion.metrics?.length > 0 && (
              <div>
                <strong>Metrics:</strong>{" "}
                {suggestion.metrics.map((m: any) => m.label).join(", ")}
              </div>
            )}
            {suggestion.group_by?.length > 0 && (
              <div>
                <strong>Group by:</strong> {suggestion.group_by.join(", ")}
              </div>
            )}
          </div>

          <button
            onClick={handleCreate}
            disabled={creating || !selectedDbId}
            style={{
              background: creating || !selectedDbId ? "#ccc" : "#52c41a",
              color: "white",
              border: "none",
              borderRadius: "4px",
              padding: "8px 16px",
              cursor: creating || !selectedDbId ? "not-allowed" : "pointer",
              fontSize: "13px",
              fontWeight: 600,
            }}
          >
            {creating ? "Creating…" : "Create Chart in Superset"}
          </button>

          {createdUrl && (
            <div
              style={{
                background: "#f6ffed",
                border: "1px solid #b7eb8f",
                borderRadius: "4px",
                padding: "8px",
                fontSize: "12px",
                color: "#389e0d",
              }}
            >
              Chart created!{" "}
              <a href={createdUrl} target="_blank" rel="noreferrer" style={{ color: "#389e0d" }}>
                Open in Explore →
              </a>
            </div>
          )}
        </div>
      )}

      <p style={{ fontSize: "11px", color: "#999", margin: 0 }}>
        Chart opens in Superset Explore for final adjustments.
      </p>
    </div>
  );
}
