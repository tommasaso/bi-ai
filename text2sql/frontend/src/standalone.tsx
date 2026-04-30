import React, { useState, useEffect } from "react";
import { AiPanel } from "./panel/AiPanel";

const PANEL_WIDTH = 320;
const STYLE_ID = "bi-ai-layout-style";

function isSqlLab(): boolean {
  return window.location.href.toLowerCase().includes("sqllab");
}

function applyLayoutStyle(active: boolean) {
  let el = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement("style");
    el.id = STYLE_ID;
    document.head.appendChild(el);
  }
  el.textContent = active
    ? `body { margin-right: ${PANEL_WIDTH}px !important; transition: margin-right 0.2s; }
       #root { max-width: 100%; }`
    : `body { margin-right: 0 !important; transition: margin-right 0.2s; }`;
}

function SidebarHost() {
  const [onSqlLab, setOnSqlLab] = useState(isSqlLab);
  const [isOpen, setIsOpen] = useState(isSqlLab); // open by default in SQL Lab

  // Watch SPA navigation (Superset uses client-side routing)
  useEffect(() => {
    const tick = () => {
      const nowOnSqlLab = isSqlLab();
      setOnSqlLab(nowOnSqlLab);
      if (nowOnSqlLab) setIsOpen(true); // re-open when navigating back to SQL Lab
    };
    const interval = setInterval(tick, 600);
    return () => clearInterval(interval);
  }, []);

  // Inject/remove layout CSS whenever open state changes
  useEffect(() => {
    applyLayoutStyle(isOpen && onSqlLab);
    return () => applyLayoutStyle(false);
  }, [isOpen, onSqlLab]);

  if (!onSqlLab) return null;

  return (
    <>
      {/* Narrow re-open tab shown only when panel is closed */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          title="Open AI assistant"
          style={{
            position: "fixed",
            right: 0,
            top: "50%",
            transform: "translateY(-50%)",
            background: "#1890ff",
            color: "white",
            border: "none",
            borderRadius: "4px 0 0 4px",
            padding: "14px 5px",
            cursor: "pointer",
            zIndex: 1001,
            writingMode: "vertical-rl",
            fontSize: "12px",
            fontWeight: 600,
            letterSpacing: "1px",
            boxShadow: "-2px 0 6px rgba(0,0,0,0.15)",
            userSelect: "none",
          }}
        >
          Ask AI
        </button>
      )}

      {/* Sidebar panel */}
      {isOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            width: `${PANEL_WIDTH}px`,
            height: "100vh",
            background: "white",
            borderLeft: "1px solid #e8e8e8",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            boxShadow: "-2px 0 8px rgba(0,0,0,0.08)",
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "10px 16px",
              borderBottom: "1px solid #f0f0f0",
              background: "#fafafa",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexShrink: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  background: "#1890ff",
                  color: "white",
                  borderRadius: "3px",
                  padding: "1px 6px",
                  fontSize: "11px",
                  fontWeight: 700,
                  letterSpacing: "0.3px",
                }}
              >
                AI
              </span>
              <span style={{ fontWeight: 600, fontSize: "14px" }}>Assistant</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              title="Minimize"
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "18px",
                color: "#bbb",
                lineHeight: 1,
                padding: "0 2px",
              }}
            >
              ›
            </button>
          </div>

          {/* Scrollable content */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            <AiPanel />
          </div>
        </div>
      )}
    </>
  );
}

function activate(mountPoint: HTMLElement) {
  const ReactDOM = require("react-dom");
  ReactDOM.render(<SidebarHost />, mountPoint);
}

(window as any).__biAiExtensions = {
  "bi-ai.text2sql": { activate },
};
