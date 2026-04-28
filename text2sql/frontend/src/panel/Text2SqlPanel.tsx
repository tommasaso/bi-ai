import React, { useState } from "react";
import { sqlLab } from "@apache-superset/core";

const EXAMPLES = [
  "Top 10 lines by average delay in the last 30 days",
  "Punctuality rate by line for the current month",
  "Daily passenger count trend over the last 60 days",
  "Lines with the most vehicle anomalies this week",
];

export function Text2SqlPanel() {
  const [question, setQuestion] = useState("");
  const [explanation, setExplanation] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    const tab = sqlLab.getCurrentTab();
    if (!tab) {
      setError("No active SQL Lab tab found.");
      return;
    }

    const databaseId = (tab as any).editor?.databaseId ?? (tab as any).databaseId;
    if (!databaseId) {
      setError("No database selected in the current tab.");
      return;
    }

    setLoading(true);
    setError("");
    setExplanation("");
    setWarnings([]);

    try {
      const response = await fetch("/extensions/bi-ai/text2sql/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ question, database_id: databaseId }),
      });

      if (response.status === 401) {
        setError("Not authenticated. Please log in to Superset.");
        return;
      }

      const result = await response.json();

      if (result.status === "success" && result.sql) {
        (sqlLab as any).setActiveEditorSql(result.sql);
        setExplanation(result.explanation || "");
        setWarnings(result.warnings || []);
      } else if (result.status === "clarification_needed") {
        setError(`Clarification needed: ${result.explanation}`);
      } else if (result.status === "unsupported") {
        setError(`Cannot answer with available data: ${result.explanation}`);
      } else {
        setError(result.explanation || "Unknown error from the AI.");
      }
    } catch (e) {
      setError("Network error. Check that Superset is running and the extension is loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px", height: "100%", boxSizing: "border-box" }}>
      <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>Ask AI</h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <label style={{ fontSize: "12px", color: "#666" }}>Examples</label>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => setQuestion(ex)}
            style={{
              textAlign: "left",
              background: "none",
              border: "1px solid #e8e8e8",
              borderRadius: "4px",
              padding: "4px 8px",
              cursor: "pointer",
              fontSize: "11px",
              color: "#1890ff",
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question about your data..."
        rows={4}
        style={{
          width: "100%",
          boxSizing: "border-box",
          padding: "8px",
          border: "1px solid #d9d9d9",
          borderRadius: "4px",
          fontSize: "13px",
          resize: "vertical",
        }}
      />

      <button
        onClick={handleGenerate}
        disabled={loading || !question.trim()}
        style={{
          background: loading || !question.trim() ? "#ccc" : "#1890ff",
          color: "white",
          border: "none",
          borderRadius: "4px",
          padding: "8px 16px",
          cursor: loading || !question.trim() ? "not-allowed" : "pointer",
          fontSize: "13px",
          fontWeight: 600,
        }}
      >
        {loading ? "Generating…" : "Generate SQL"}
      </button>

      {error && (
        <div style={{ background: "#fff2f0", border: "1px solid #ffccc7", borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#cf1322" }}>
          {error}
        </div>
      )}

      {explanation && (
        <div style={{ background: "#f6ffed", border: "1px solid #b7eb8f", borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#389e0d" }}>
          <strong>✓ SQL generated</strong>
          <p style={{ margin: "4px 0 0" }}>{explanation}</p>
        </div>
      )}

      {warnings.length > 0 && (
        <div style={{ background: "#fffbe6", border: "1px solid #ffe58f", borderRadius: "4px", padding: "8px", fontSize: "12px", color: "#d48806" }}>
          <strong>Warnings</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: "16px" }}>
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <p style={{ fontSize: "11px", color: "#999", margin: 0 }}>
        SQL is placed in the editor but never executed automatically.
      </p>
    </div>
  );
}
