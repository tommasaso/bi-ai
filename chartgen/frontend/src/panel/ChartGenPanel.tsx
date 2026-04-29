import React, { useState, useEffect, useRef, useCallback } from "react";
import { sqlLab } from "@apache-superset/core";

type Column = { name: string; type: string };

type Metric = { label: string; expressionType: string; sqlExpression: string };

type ChartSuggestion = {
  viz_type: string;
  title: string;
  x_axis?: string;
  metrics: Metric[];
  group_by: string[];
  time_grain_sqla?: string;
  explanation: string;
};

type QueryContext = {
  sql: string;
  columns: Column[];
  databaseId: number;
};

const VIZ_LABELS: Record<string, string> = {
  echarts_timeseries_line: "Line chart",
  echarts_bar: "Bar chart",
  pie: "Pie chart",
  table: "Table",
  big_number_total: "Big Number",
};

const s = {
  root: { padding: "16px", display: "flex", flexDirection: "column" as const, gap: "12px", height: "100%", boxSizing: "border-box" as const },
  h3: { margin: 0, fontSize: "14px", fontWeight: 600 },
  muted: { fontSize: "12px", color: "#999", margin: 0 },
  card: { background: "#fafafa", border: "1px solid #e8e8e8", borderRadius: "6px", padding: "10px 12px" },
  label: { fontSize: "11px", color: "#888", textTransform: "uppercase" as const, letterSpacing: "0.5px", marginBottom: "4px" },
  value: { fontSize: "13px", fontWeight: 500, color: "#1a1a1a" },
  explanation: { fontSize: "12px", color: "#595959", marginTop: "6px", lineHeight: 1.5 },
  pill: { display: "inline-block", background: "#e6f4ff", color: "#0958d9", borderRadius: "4px", padding: "2px 8px", fontSize: "11px", marginRight: "4px", marginBottom: "4px" },
  refineRow: { display: "flex", gap: "6px" },
  input: { flex: 1, padding: "7px 10px", border: "1px solid #d9d9d9", borderRadius: "4px", fontSize: "13px", outline: "none" },
  btnPrimary: (disabled: boolean) => ({
    background: disabled ? "#ccc" : "#1890ff",
    color: "white", border: "none", borderRadius: "4px",
    padding: "7px 14px", cursor: disabled ? "not-allowed" : "pointer",
    fontSize: "13px", fontWeight: 600, whiteSpace: "nowrap" as const,
  }),
  btnSecondary: (disabled: boolean) => ({
    background: "none", border: "1px solid #d9d9d9", borderRadius: "4px",
    padding: "7px 12px", cursor: disabled ? "not-allowed" : "pointer",
    fontSize: "12px", color: disabled ? "#ccc" : "#595959",
  }),
  success: { background: "#f6ffed", border: "1px solid #b7eb8f", borderRadius: "4px", padding: "10px 12px", fontSize: "12px", color: "#389e0d" },
  error: { background: "#fff2f0", border: "1px solid #ffccc7", borderRadius: "4px", padding: "8px 12px", fontSize: "12px", color: "#cf1322" },
  warning: { background: "#fffbe6", border: "1px solid #ffe58f", borderRadius: "4px", padding: "8px 12px", fontSize: "12px", color: "#d48806" },
  spinner: { display: "inline-block", width: "12px", height: "12px", border: "2px solid #e8e8e8", borderTopColor: "#1890ff", borderRadius: "50%", animation: "spin 0.7s linear infinite", marginRight: "6px" },
};

export function ChartGenPanel() {
  const [queryCtx, setQueryCtx] = useState<QueryContext | null>(null);
  const [suggestion, setSuggestion] = useState<ChartSuggestion | null>(null);
  const [refineInput, setRefineInput] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [exploreUrl, setExploreUrl] = useState("");
  const [error, setError] = useState("");
  const latestCtxRef = useRef<QueryContext | null>(null);

  const autoSuggest = useCallback(async (ctx: QueryContext, question = "") => {
    setSuggesting(true);
    setError("");
    setSuggestion(null);
    setExploreUrl("");
    try {
      const resp = await fetch("/extensions/bi-ai/chartgen/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          sql: ctx.sql,
          columns: ctx.columns,
          database_id: ctx.databaseId,
          question,
        }),
      });
      if (resp.status === 401) { setError("Not authenticated."); return; }
      const result = await resp.json();
      if (result.status === "success") {
        setSuggestion(result);
      } else {
        setError(result.explanation || "Could not suggest a chart.");
      }
    } catch {
      setError("Network error contacting chart suggest endpoint.");
    } finally {
      setSuggesting(false);
    }
  }, []);

  useEffect(() => {
    const disposable = (sqlLab as any).onDidQuerySuccess((ctx: any) => {
      const columns: Column[] = (ctx.result?.columns ?? []).map((c: any) => ({
        name: c.name || c.column_name || "",
        type: c.type || "STRING",
      }));
      const sql: string = ctx.executedSql ?? ctx.tab?.editor?.content ?? "";
      const databaseId: number = ctx.tab?.editor?.databaseId;
      if (!sql || !databaseId) return;
      const newCtx = { sql, columns, databaseId };
      setQueryCtx(newCtx);
      latestCtxRef.current = newCtx;
      setRefineInput("");
      autoSuggest(newCtx, "");
    });
    return () => disposable.dispose();
  }, [autoSuggest]);

  async function handleRefine() {
    if (!queryCtx || !refineInput.trim()) return;
    const question = suggestion
      ? `${refineInput}. Previous suggestion: ${suggestion.viz_type} titled "${suggestion.title}"`
      : refineInput;
    await autoSuggest(queryCtx, question);
    setRefineInput("");
  }

  async function handleCreate() {
    if (!queryCtx || !suggestion) return;
    setCreating(true);
    setError("");
    try {
      const resp = await fetch("/extensions/bi-ai/chartgen/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          sql: queryCtx.sql,
          database_id: queryCtx.databaseId,
          suggestion,
        }),
      });
      if (resp.status === 401) { setError("Not authenticated."); return; }
      const result = await resp.json();
      if (result.explore_url) {
        setExploreUrl(result.explore_url);
      } else {
        setError(result.error || "Failed to create chart.");
      }
    } catch {
      setError("Network error creating chart.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div style={s.root}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <h3 style={s.h3}>AI Chart</h3>

      {!queryCtx && !suggesting && (
        <p style={s.muted}>Run a query in SQL Lab to generate a chart suggestion.</p>
      )}

      {suggesting && (
        <div style={{ display: "flex", alignItems: "center", fontSize: "13px", color: "#595959" }}>
          <span style={s.spinner} />
          Analysing query…
        </div>
      )}

      {suggestion && !suggesting && (
        <>
          <div style={s.card}>
            <div style={s.label}>Chart type</div>
            <div style={s.value}>{VIZ_LABELS[suggestion.viz_type] ?? suggestion.viz_type}</div>

            <div style={{ ...s.label, marginTop: "10px" }}>Title</div>
            <div style={s.value}>{suggestion.title}</div>

            {suggestion.x_axis && (
              <>
                <div style={{ ...s.label, marginTop: "10px" }}>X axis / time</div>
                <div style={s.value}>{suggestion.x_axis}</div>
              </>
            )}

            {suggestion.metrics.length > 0 && (
              <>
                <div style={{ ...s.label, marginTop: "10px" }}>Metrics</div>
                {suggestion.metrics.map((m, i) => (
                  <span key={i} style={s.pill}>{m.label}</span>
                ))}
              </>
            )}

            {suggestion.group_by.length > 0 && (
              <>
                <div style={{ ...s.label, marginTop: "10px" }}>Group by</div>
                {suggestion.group_by.map((g, i) => (
                  <span key={i} style={{ ...s.pill, background: "#f9f0ff", color: "#531dab" }}>{g}</span>
                ))}
              </>
            )}

            <div style={s.explanation}>{suggestion.explanation}</div>
          </div>

          <div style={s.refineRow}>
            <input
              style={s.input}
              value={refineInput}
              onChange={e => setRefineInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleRefine()}
              placeholder='Refine: "make it a bar chart", "group by week"…'
            />
            <button
              style={s.btnSecondary(!refineInput.trim() || suggesting)}
              disabled={!refineInput.trim() || suggesting}
              onClick={handleRefine}
            >
              Refine
            </button>
          </div>

          {!exploreUrl && (
            <button
              style={s.btnPrimary(creating)}
              disabled={creating}
              onClick={handleCreate}
            >
              {creating ? "Creating chart…" : "Create Chart ↗"}
            </button>
          )}
        </>
      )}

      {exploreUrl && (
        <div style={s.success}>
          <strong>Chart created!</strong>
          <div style={{ marginTop: "6px" }}>
            <a href={exploreUrl} target="_blank" rel="noreferrer"
              style={{ color: "#389e0d", fontWeight: 600 }}>
              Open in Explore ↗
            </a>
          </div>
        </div>
      )}

      {error && <div style={s.error}>{error}</div>}

      <p style={s.muted}>Chart is created as a new virtual dataset. Run a new query to start over.</p>
    </div>
  );
}
