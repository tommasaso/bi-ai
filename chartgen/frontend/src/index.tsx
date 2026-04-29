import React from "react";
import * as superset from "@apache-superset/core";
import { ChartGenPanel } from "./panel/ChartGenPanel";

export function activate(context: { disposables: { dispose: () => any }[] }) {
  const disposable = (superset as any).core.registerViewProvider(
    "bi-ai.chartgen.panel",
    () => <ChartGenPanel />,
  );
  context.disposables.push(disposable);
}

export function deactivate() {}
