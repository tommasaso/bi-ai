import React, { useState, useEffect } from "react";

const EXAMPLES = [
  "Top 10 lines by average delay in the last 30 days",
  "Punctuality rate by line for the current month",
  "Daily passenger count trend over the last 60 days",
  "Completion rate per line this month",
];

const VIZ_LABELS: Record<string, string> = {
  echarts_timeseries_line: "Line Chart",
  echarts_timeseries_bar: "Bar Chart",
  echarts_bar: "Bar Chart",
  pie: "Pie Chart",
  table: "Table",
  big_number_total: "Big Number",
};

interface Database {
  id: number;
  name: string;
}

function tryInjectSql(sql: string) {
  try {
    const ace = (window as any).ace;
    if (ace) {
      const editors = document.querySelectorAll(".ace_editor");
      if (editors.length > 0) {
        ace.edit(editors[editors.length - 1] as HTMLElement).setValue(sql, -1);
      }
    }
  } catch (_) {}
}

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

const divider = (
  <div
    style={{
      borderTop: "1px solid #f0f0f0",
      margin: "4px -16px",
      padding: "8px 16px 0",
    }}
  />
);

export function AiPanel() {
  // Shared
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);

  // Ask AI
  const [question, setQuestion] = useState("");
  const [generatedSql, setGeneratedSql] = useState("");
  const [explanation, setExplanation] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [sqlLoading, setSqlLoading] = useState(false);
  const [sqlError, setSqlError] = useState("");
  const [copied, setCopied] = useState(false);

  // Chart AI
  const [chartSql, setChartSql] = useState("");
  const [chartIntent, setChartIntent] = useState("");
  const [chartSuggestion, setChartSuggestion] = useState<any>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartCreating, setChartCreating] = useState(false);
  const [chartError, setChartError] = useState("");
  const [chartUrl, setChartUrl] = useState("");

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
  }, []);

  // Auto-populate chart SQL when Ask AI generates one
  useEffect(() => {
    if (generatedSql) {
      setChartSql(generatedSql);
      setChartSuggestion(null);
      setChartUrl("");
      setChartError("");
    }
  }, [generatedSql]);

  // ── Ask AI handlers ──────────────────────────────────────────────────────

  async function handleGenerateSql() {
    if (!selectedDbId) { setSqlError("Select a database first."); return; }
    setSqlLoading(true);
    setSqlError(""); setGeneratedSql(""); setExplanation(""); setWarnings([]); setCopied(false);

    try {
      const r = await fetch("/api/v1/bi-ai/text2sql/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ question, database_id: selectedDbId }),
      });
      if (r.status === 401) { setSqlError("Not authenticated."); return; }
      const result = await r.json();
      if (result.status === "success" && result.sql) {
        setGeneratedSql(result.sql);
        setExplanation(result.explanation || "");
        setWarnings(result.warnings || []);
        tryInjectSql(result.sql);
      } else if (result.status === "clarification_needed") {
        setSqlError(`Clarification needed: ${result.explanation}`);
      } else {
        setSqlError(result.explanation || "Unknown error from the AI.");
      }
    } catch { setSqlError("Network error."); }
    finally { setSqlLoading(false); }
  }

  function handleCopySql() {
    navigator.clipboard?.writeText(generatedSql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }

  // ── Chart AI handlers ────────────────────────────────────────────────────

  function handleLoadFromEditor() {
    const s = readSqlFromEditor();
    if (s.trim()) {
      setChartSql(s);
      setChartSuggestion(null);
      setChartUrl("");
      setChartError("");
    }
  }

  async function handleSuggestChart() {
    if (!chartSql.trim()) { setChartError("No SQL to analyze."); return; }
    setChartLoading(true);
    setChartError(""); setChartSuggestion(null); setChartUrl("");

    try {
      const r = await fetch("/api/v1/bi-ai/chartgen/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ sql: chartSql, columns: [], question: chartIntent }),
      });
      if (r.status === 401) { setChartError("Not authenticated."); return; }
      const result = await r.json();
      if (result.status === "success") {
        setChartSuggestion(result);
      } else {
        setChartError(result.explanation || "Could not suggest a chart.");
      }
    } catch { setChartError("Network error."); }
    finally { setChartLoading(false); }
  }

  async function handleCreateChart() {
    if (!chartSuggestion || !selectedDbId) return;
    setChartCreating(true); setChartError("");

    try {
      const r = await fetch("/api/v1/bi-ai/chartgen/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ sql: chartSql, database_id: selectedDbId, suggestion: chartSuggestion }),
      });
      const result = await r.json();
      if (result.explore_url) {
        setChartUrl(result.explore_url);
        window.open(result.explore_url, "_blank");
      } else {
        setChartError(result.error || "Could not create chart.");
      }
    } catch { setChartError("Network error."); }
    finally { setChartCreating(false); }
  }

  // ── Styles ───────────────────────────────────────────────────────────────

  const sectionLabel: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 700,
    color: "#888",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    margin: "0 0 8px",
  };

  const errorBox: React.CSSProperties = {
    background: "#fff2f0", border: "1px solid #ffccc7",
    borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#cf1322",
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>

      {/* Database selector — shared */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <label style={{ fontSize: "12px", color: "#666" }}>Database</label>
        <select
          value={selectedDbId ?? ""}
          onChange={(e) => setSelectedDbId(Number(e.target.value))}
          style={{ padding: "6px 8px", border: "1px solid #d9d9d9", borderRadius: "4px", fontSize: "13px" }}
        >
          {databases.length === 0 && <option value="">Loading…</option>}
          {databases.map((db) => (
            <option key={db.id} value={db.id}>{db.name}</option>
          ))}
        </select>
      </div>

      {/* ── Ask AI section ── */}
      <p style={sectionLabel}>Ask AI</p>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <label style={{ fontSize: "12px", color: "#666" }}>Examples</label>
        {EXAMPLES.map((ex) => (
          <button key={ex} onClick={() => setQuestion(ex)} style={{
            textAlign: "left", background: "none", border: "1px solid #e8e8e8",
            borderRadius: "4px", padding: "4px 8px", cursor: "pointer",
            fontSize: "11px", color: "#1890ff",
          }}>
            {ex}
          </button>
        ))}
      </div>

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question about your data…"
        rows={3}
        style={{
          width: "100%", boxSizing: "border-box", padding: "8px",
          border: "1px solid #d9d9d9", borderRadius: "4px", fontSize: "13px", resize: "vertical",
        }}
      />

      <button
        onClick={handleGenerateSql}
        disabled={sqlLoading || !question.trim()}
        style={{
          background: sqlLoading || !question.trim() ? "#ccc" : "#1890ff",
          color: "white", border: "none", borderRadius: "4px",
          padding: "8px 16px", cursor: sqlLoading || !question.trim() ? "not-allowed" : "pointer",
          fontSize: "13px", fontWeight: 600,
        }}
      >
        {sqlLoading ? "Generating…" : "Generate SQL"}
      </button>

      {sqlError && <div style={errorBox}>{sqlError}</div>}

      {generatedSql && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {explanation && (
            <div style={{
              background: "#f6ffed", border: "1px solid #b7eb8f",
              borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#389e0d",
            }}>
              {explanation}
            </div>
          )}
          <div style={{ position: "relative" }}>
            <pre style={{
              background: "#f5f5f5", border: "1px solid #e8e8e8", borderRadius: "4px",
              padding: "8px", fontSize: "11px", margin: 0, overflow: "auto",
              maxHeight: "140px", whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {generatedSql}
            </pre>
            <button onClick={handleCopySql} style={{
              position: "absolute", top: "6px", right: "6px",
              background: copied ? "#52c41a" : "#fff", border: "1px solid #d9d9d9",
              borderRadius: "4px", padding: "2px 8px", cursor: "pointer",
              fontSize: "11px", color: copied ? "white" : "#666",
            }}>
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          {warnings.length > 0 && (
            <div style={{
              background: "#fffbe6", border: "1px solid #ffe58f",
              borderRadius: "4px", padding: "8px", fontSize: "11px", color: "#d48806",
            }}>
              {warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
        </div>
      )}

      {divider}

      {/* ── Chart AI section ── */}
      <p style={sectionLabel}>Chart AI</p>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label style={{ fontSize: "12px", color: "#666" }}>SQL</label>
          <button onClick={handleLoadFromEditor} style={{
            background: "none", border: "1px solid #d9d9d9", borderRadius: "4px",
            padding: "2px 8px", cursor: "pointer", fontSize: "11px", color: "#666",
          }}>
            Load from editor
          </button>
        </div>
        <textarea
          value={chartSql}
          onChange={(e) => setChartSql(e.target.value)}
          placeholder="Generated SQL appears here, or load from editor…"
          rows={4}
          style={{
            width: "100%", boxSizing: "border-box", padding: "8px",
            border: "1px solid #d9d9d9", borderRadius: "4px",
            fontSize: "11px", resize: "vertical", fontFamily: "monospace",
            color: "#444",
          }}
        />
      </div>

      <input
        type="text"
        value={chartIntent}
        onChange={(e) => setChartIntent(e.target.value)}
        placeholder="What to show? e.g. trend over time… (optional)"
        style={{
          padding: "6px 8px", border: "1px solid #d9d9d9",
          borderRadius: "4px", fontSize: "12px",
        }}
      />

      <button
        onClick={handleSuggestChart}
        disabled={chartLoading || !chartSql.trim()}
        style={{
          background: chartLoading || !chartSql.trim() ? "#ccc" : "#722ed1",
          color: "white", border: "none", borderRadius: "4px",
          padding: "8px 16px", cursor: chartLoading || !chartSql.trim() ? "not-allowed" : "pointer",
          fontSize: "13px", fontWeight: 600,
        }}
      >
        {chartLoading ? "Analyzing…" : "Suggest Chart"}
      </button>

      {chartError && <div style={errorBox}>{chartError}</div>}

      {chartSuggestion && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{
              background: "#f9f0ff", border: "1px solid #d3adf7",
              borderRadius: "4px", padding: "2px 10px",
              fontSize: "12px", color: "#722ed1", fontWeight: 600,
            }}>
              {VIZ_LABELS[chartSuggestion.viz_type] ?? chartSuggestion.viz_type}
            </span>
            <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
              {chartSuggestion.title}
            </span>
          </div>

          {chartSuggestion.explanation && (
            <div style={{
              background: "#f6ffed", border: "1px solid #b7eb8f",
              borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#389e0d",
            }}>
              {chartSuggestion.explanation}
            </div>
          )}

          <div style={{
            background: "#fafafa", border: "1px solid #f0f0f0",
            borderRadius: "4px", padding: "8px", fontSize: "11px", color: "#666", lineHeight: 1.6,
          }}>
            {chartSuggestion.x_axis && <div><strong>X-axis:</strong> {chartSuggestion.x_axis}</div>}
            {chartSuggestion.metrics?.length > 0 && (
              <div><strong>Metrics:</strong> {chartSuggestion.metrics.map((m: any) => m.label).join(", ")}</div>
            )}
            {chartSuggestion.group_by?.length > 0 && (
              <div><strong>Group by:</strong> {chartSuggestion.group_by.join(", ")}</div>
            )}
          </div>

          <button
            onClick={handleCreateChart}
            disabled={chartCreating || !selectedDbId}
            style={{
              background: chartCreating || !selectedDbId ? "#ccc" : "#52c41a",
              color: "white", border: "none", borderRadius: "4px",
              padding: "8px 16px", cursor: chartCreating || !selectedDbId ? "not-allowed" : "pointer",
              fontSize: "13px", fontWeight: 600,
            }}
          >
            {chartCreating ? "Creating…" : "Create Chart in Superset"}
          </button>

          {chartUrl && (
            <div style={{
              background: "#f6ffed", border: "1px solid #b7eb8f",
              borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#389e0d",
            }}>
              Chart created!{" "}
              <a href={chartUrl} target="_blank" rel="noreferrer" style={{ color: "#389e0d" }}>
                Open in Explore →
              </a>
            </div>
          )}
        </div>
      )}

      <p style={{ fontSize: "11px", color: "#999", margin: 0 }}>
        SQL is injected into the editor automatically.
      </p>
    </div>
  );
}
