import React, { useState, useEffect } from "react";

const EXAMPLES = [
  "Top 10 lines by average delay in the last 30 days",
  "Punctuality rate by line for the current month",
  "Daily passenger count trend over the last 60 days",
  "Lines with the most vehicle anomalies this week",
];

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
        const editor = ace.edit(editors[editors.length - 1] as HTMLElement);
        editor.setValue(sql, -1);
      }
    }
  } catch (_) {}
}

export function Text2SqlPanel() {
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [generatedSql, setGeneratedSql] = useState("");
  const [explanation, setExplanation] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

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

  async function handleGenerate() {
    if (!selectedDbId) {
      setError("Select a database first.");
      return;
    }

    setLoading(true);
    setError("");
    setGeneratedSql("");
    setExplanation("");
    setWarnings([]);
    setCopied(false);

    try {
      const response = await fetch("/api/v1/bi-ai/text2sql/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ question, database_id: selectedDbId }),
      });

      if (response.status === 401) {
        setError("Not authenticated. Please log in to Superset.");
        return;
      }

      const result = await response.json();

      if (result.status === "success" && result.sql) {
        setGeneratedSql(result.sql);
        setExplanation(result.explanation || "");
        setWarnings(result.warnings || []);
        tryInjectSql(result.sql);
      } else if (result.status === "clarification_needed") {
        setError(`Clarification needed: ${result.explanation}`);
      } else if (result.status === "unsupported") {
        setError(`Cannot answer with available data: ${result.explanation}`);
      } else {
        setError(result.explanation || "Unknown error from the AI.");
      }
    } catch (e) {
      setError("Network error. Check that the extension is loaded.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    navigator.clipboard
      ?.writeText(generatedSql)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
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
          {databases.length === 0 && (
            <option value="">Loading databases…</option>
          )}
          {databases.map((db) => (
            <option key={db.id} value={db.id}>
              {db.name}
            </option>
          ))}
        </select>
      </div>

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
        placeholder="Ask a question about your data…"
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

      {generatedSql && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {explanation && (
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
              {explanation}
            </div>
          )}

          <div style={{ position: "relative" }}>
            <pre
              style={{
                background: "#f5f5f5",
                border: "1px solid #e8e8e8",
                borderRadius: "4px",
                padding: "8px",
                fontSize: "12px",
                margin: 0,
                overflow: "auto",
                maxHeight: "200px",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {generatedSql}
            </pre>
            <button
              onClick={handleCopy}
              style={{
                position: "absolute",
                top: "6px",
                right: "6px",
                background: copied ? "#52c41a" : "#fff",
                border: "1px solid #d9d9d9",
                borderRadius: "4px",
                padding: "2px 8px",
                cursor: "pointer",
                fontSize: "11px",
                color: copied ? "white" : "#666",
              }}
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          {warnings.length > 0 && (
            <div
              style={{
                background: "#fffbe6",
                border: "1px solid #ffe58f",
                borderRadius: "4px",
                padding: "8px",
                fontSize: "12px",
                color: "#d48806",
              }}
            >
              <strong>Warnings</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: "16px" }}>
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <p style={{ fontSize: "11px", color: "#999", margin: 0 }}>
        SQL is placed in the editor automatically. Use Copy if it doesn't appear.
      </p>
    </div>
  );
}
