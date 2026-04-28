import React from "react";
import * as superset from "@apache-superset/core";
import { Text2SqlPanel } from "./panel/Text2SqlPanel";

export function activate(context: { disposables: { dispose: () => any }[] }) {
  const disposable = (superset as any).core.registerViewProvider(
    "bi-ai.text2sql.panel",
    () => <Text2SqlPanel />,
  );
  context.disposables.push(disposable);
}

export function deactivate() {}
