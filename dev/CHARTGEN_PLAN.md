# Implementation Plan: bi-ai.chartgen — AI-Assisted Chart Generation

**Status:** Ready to implement  
**Constraint:** Modifiche SOLO in `bi-ai/` — nessun tocco a apache-superset, kpi-proxy, bi-tool, bi-user-management-adapter  
**Obiettivo:** Secondo plugin Superset che, dopo l'esecuzione di una query SQL in SQL Lab, propone e crea un chart via LLM + linguaggio naturale

---

## Architettura

```
SQL Lab (utente esegue query)
  → onDidQuerySuccess fires → ChartGenPanel riceve SQL + colonne + question
  → Pannello mostra proposta LLM (viz_type, metriche, dimensioni, titolo)
  → Utente può raffinare in NL ("rendilo un bar chart", "aggrega per settimana")
  → LLM aggiorna la proposta
  → "Create Chart" → POST /extensions/bi-ai/chartgen/create
    → Backend crea virtual dataset (SQL) + chart (Slice) via Superset ORM
    → Ritorna URL Explore
  → Frontend naviga a /explore/?slice_id=<id>
```

---

## Struttura file

```
bi-ai/
└── chartgen/
    ├── extension.json
    ├── frontend/
    │   ├── package.json
    │   ├── tsconfig.json
    │   ├── webpack.config.js
    │   └── src/
    │       ├── index.tsx                    ← activate() + registerViewProvider
    │       └── panel/
    │           └── ChartGenPanel.tsx        ← componente React principale
    └── backend/
        └── src/
            └── bi_ai/
                └── chartgen/
                    ├── __init__.py
                    ├── entrypoint.py        ← from . import api
                    ├── api.py               ← /suggest + /create endpoints
                    ├── chart_prompt.py      ← system prompt + output format LLM
                    └── chart_builder.py     ← assembla form_data + crea ORM objects
```

---

## Phase 0: Allowed APIs (da subagent research)

### Superset Extension API (frontend)
- **Source:** `/Users/tommasoelia/Git/apache-superset/superset-frontend/src/core/sqlLab/index.ts`
- `sqlLab.onDidQuerySuccess(listener)` → listener riceve `QueryResultContext`
  - `context.executedSql: string` — SQL eseguito
  - `context.result.columns: Array<{name, type}>` — colonne del risultato
  - `context.tab.editor.databaseId: number` — database ID
  - Ritorna `Disposable` → pushare a `context.disposables`
- `core.registerViewProvider(viewId, componentFactory)` — registra pannello sidebar
- **Extension point:** `"sqllab.rightSidebar"` (source: `contributions.ts`)

### Superset ORM (backend, dentro il processo Flask)
- Crea virtual dataset: `superset.connectors.sqla.models.SqlaTable`
- Crea chart: `superset.models.slice.Slice`
- Persistenza: `from superset import db; db.session.add(obj); db.session.commit()`
- Explore URL: `/explore/?slice_id={id}` o `/explore/?datasource_id={id}&datasource_type=table`

### REST API chart (fonte: `superset/charts/schemas.py` + `api.py`)
- POST `/api/v1/chart/` — campi obbligatori: `slice_name`, `datasource_id`, `datasource_type`
- `params` = JSON string con `form_data`
- `datasource` in form_data = `"{id}__table"` (formato string)

### Anti-patterns da evitare
- NON fare HTTP calls back a Superset da dentro il backend extension (usare ORM diretto)
- NON usare `get_view_names` senza passare `schema=`
- NON inventare viz_type — usare solo: `echarts_timeseries_line`, `echarts_bar`, `pie`, `table`, `big_number_total`
- NON dimenticare `library: { type: "global" }` in ModuleFederationPlugin

---

## Phase 1: Scaffold — extension.json + webpack + entrypoint

**Obiettivo:** Struttura base del plugin funzionante (pannello vuoto visibile in SQL Lab)

### 1.1 `chartgen/extension.json`
Copia da `text2sql/extension.json` e modifica:
```json
{
  "publisher": "bi-ai",
  "name": "chartgen",
  "displayName": "BI-AI Chart Generator",
  "version": "0.1.0",
  "license": "Apache-2.0",
  "permissions": ["can_read"],
  "frontend": {
    "moduleFederation": {
      "name": "bi_ai_chartgen",
      "exposes": { "./index": "./src/index.tsx" }
    },
    "contributions": {
      "views": [
        {
          "id": "bi-ai.chartgen.panel",
          "name": "AI Chart",
          "extensionPoint": "sqllab.rightSidebar"
        }
      ]
    }
  },
  "backend": {
    "entryPoint": "bi_ai.chartgen.entrypoint",
    "files": ["src/bi_ai/chartgen/**/*.py"]
  }
}
```

### 1.2 `chartgen/frontend/webpack.config.js`
Copia da `text2sql/frontend/webpack.config.js` — cambia solo il reference a `extension.json`:
- `name: "bi-ai.chartgen"`
- `library: { type: "global", name: "bi-ai.chartgen" }`
- `publicPath` rimane la stessa formula: `/api/v1/extensions/${publisher}.${name}/`

### 1.3 `chartgen/frontend/src/index.tsx`
```typescript
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
```

### 1.4 `chartgen/backend/src/bi_ai/chartgen/entrypoint.py`
```python
from . import api  # noqa: F401
```

### 1.5 `ChartGenPanel.tsx` (placeholder)
Componente vuoto che mostra "AI Chart — run a query first"

### Verifica Phase 1
```bash
cd chartgen/frontend && npm run build
# Deve compilare senza errori
# dist/ contiene remoteEntry.[hash].js
```

---

## Phase 2: Backend — `/suggest` e `/create` endpoints

**Obiettivo:** Due endpoint nel backend extension

### 2.1 `chart_prompt.py` — prompt LLM per suggerire chart

**System prompt** deve includere:
- Lista viz_type disponibili con quando usarli
- Schema output JSON atteso
- Regole: time series → line, ranking/confronto → bar, proporzioni → pie, singola metrica → big_number_total, dati tabulari → table

**Output format LLM:**
```json
{
  "status": "success",
  "viz_type": "echarts_timeseries_line",
  "title": "Average delay by line — last 30 days",
  "x_axis": "event_timestamp",
  "metrics": [
    { "label": "Avg delay (s)", "expressionType": "SQL", "sqlExpression": "AVG(mean_in_value)" }
  ],
  "group_by": ["line_id"],
  "time_grain_sqla": "P1W",
  "explanation": "A line chart showing weekly trend per line makes sense for a time series question."
}
```

### 2.2 `chart_builder.py` — assembla form_data + crea ORM objects

**Template form_data per viz_type:**

```python
BASE_FORM_DATA = {
    "adhoc_filters": [],
    "row_limit": 10000,
    "color_scheme": "supersetColors",
    "show_legend": True,
}

TEMPLATES = {
    "echarts_timeseries_line": {
        **BASE_FORM_DATA,
        "granularity_sqla": None,   # <- x_axis dal LLM
        "time_grain_sqla": "P1W",
        "metrics": [],              # <- dal LLM
        "groupby": [],              # <- group_by dal LLM
    },
    "echarts_bar": {
        **BASE_FORM_DATA,
        "metrics": [],
        "groupby": [],
        "x_axis": None,
    },
    "pie": {
        **BASE_FORM_DATA,
        "metric": None,
        "groupby": [],
    },
    "table": {
        **BASE_FORM_DATA,
        "all_columns": [],          # <- tutte le colonne del risultato
        "order_by_cols": [],
    },
    "big_number_total": {
        **BASE_FORM_DATA,
        "metric": None,
    },
}
```

**Funzione `create_chart_from_suggestion`:**
```python
def create_chart_from_suggestion(
    sql: str,
    database_id: int,
    suggestion: dict,
    owner_id: int,
) -> dict:
    """
    1. Crea SqlaTable (virtual dataset) con il SQL
    2. Assembla form_data dal template + suggestion LLM
    3. Crea Slice (chart) con form_data
    4. Ritorna {"chart_id": int, "explore_url": str}
    """
    from superset import db
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.slice import Slice
    import json

    # 1. Virtual dataset
    dataset = SqlaTable(
        table_name=suggestion["title"][:100],
        sql=sql,
        database_id=database_id,
        schema="goldlayer",
    )
    db.session.add(dataset)
    db.session.flush()  # ottieni dataset.id

    # 2. form_data
    viz_type = suggestion.get("viz_type", "table")
    form_data = _build_form_data(viz_type, suggestion, dataset.id)

    # 3. Chart
    chart = Slice(
        slice_name=suggestion["title"],
        datasource_id=dataset.id,
        datasource_type="table",
        viz_type=viz_type,
        params=json.dumps(form_data),
        created_by_fk=owner_id,
    )
    db.session.add(chart)
    db.session.commit()

    return {
        "chart_id": chart.id,
        "explore_url": f"/explore/?slice_id={chart.id}",
    }
```

### 2.3 `api.py` — due endpoint

```python
class ChartGenAPI(RestApi):
    resource_name = "bi-ai/chartgen"

    @expose("/suggest", methods=("POST",))
    @protect()
    @safe
    def suggest(self) -> Response:
        """
        Input: { sql, columns: [{name, type}], question, database_id }
        Output: { status, viz_type, title, x_axis, metrics, group_by, explanation }
        """

    @expose("/create", methods=("POST",))
    @protect()
    @safe
    def create(self) -> Response:
        """
        Input: { sql, database_id, suggestion: {viz_type, title, metrics, ...} }
        Output: { chart_id, explore_url }
        """
```

### Verifica Phase 2
```bash
# Con Superset running:
curl -X POST http://localhost:8088/extensions/bi-ai/chartgen/suggest \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT line_id, AVG(mean_in_value) FROM goldlayer.delay_vw WHERE tenant_id=1 GROUP BY line_id", "columns": [{"name":"line_id","type":"STRING"},{"name":"avg","type":"FLOAT"}], "question": "average delay by line", "database_id": 3}'
# Deve ritornare JSON con viz_type, title, metrics
```

---

## Phase 3: Frontend — ChartGenPanel React component

**Obiettivo:** Pannello completo con stato, subscription agli eventi query, NL refinement

### Stato del componente
```typescript
type ChartSuggestion = {
  viz_type: string;
  title: string;
  x_axis?: string;
  metrics: { label: string; sqlExpression: string }[];
  group_by: string[];
  explanation: string;
};

const [queryContext, setQueryContext] = useState<{
  sql: string;
  columns: { name: string; type: string }[];
  databaseId: number;
  question?: string;
} | null>(null);

const [suggestion, setSuggestion] = useState<ChartSuggestion | null>(null);
const [refineInput, setRefineInput] = useState("");
const [loading, setLoading] = useState(false);
const [creating, setCreating] = useState(false);
```

### Subscription a onDidQuerySuccess
```typescript
useEffect(() => {
  const { sqlLab } = (window as any).superset;
  const disposable = sqlLab.onDidQuerySuccess((ctx: any) => {
    const columns = ctx.result?.columns ?? [];
    const sql = ctx.executedSql ?? "";
    const databaseId = ctx.tab?.editor?.databaseId;
    setQueryContext({ sql, columns, databaseId });
    // Auto-suggest se c'è SQL
    if (sql && databaseId) autoSuggest(sql, columns, databaseId);
  });
  return () => disposable.dispose();
}, []);
```

### Flow NL refinement
1. Utente vede proposta → può digitare "rendilo un bar chart" → click "Refine"
2. Chiama `/suggest` di nuovo passando `question = refineInput + " (previous suggestion: " + JSON.stringify(suggestion) + ")"`
3. LLM risponde con nuova suggestion

### "Create Chart" button
```typescript
async function handleCreate() {
  setCreating(true);
  const resp = await fetch("/extensions/bi-ai/chartgen/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      sql: queryContext.sql,
      database_id: queryContext.databaseId,
      suggestion,
    }),
  });
  const result = await resp.json();
  if (result.explore_url) {
    window.open(result.explore_url, "_blank");
  }
  setCreating(false);
}
```

### Layout UI (no external CSS)
```
┌─────────────────────────────┐
│ AI Chart                    │  ← header
├─────────────────────────────┤
│ Run a query to get started  │  ← stato vuoto
│                             │
│ ─── dopo query success ───  │
│                             │
│ Suggested chart:            │
│ 📊 echarts_timeseries_line  │
│ "Avg delay by line"         │
│ X: event_timestamp          │
│ Y: AVG(mean_in_value)       │
│ Group: line_id              │
│                             │
│ [explanation text]          │
│                             │
│ Refine:                     │
│ [input NL            ] [→]  │
│                             │
│ [Create Chart ↗]            │
└─────────────────────────────┘
```

### Verifica Phase 3
- Playwright: login → SQL Lab → run query → check "AI Chart" panel visible
- Verify suggestion appears after query success
- Verify "Create Chart" navigates to Explore

---

## Phase 4: Packaging

### 4.1 Crea `chartgen/chartgen-0.1.0.supx`
Stesso processo di text2sql:

```bash
cd chartgen

# 1. Build frontend
cd frontend && npm install && npm run build && cd ..

# 2. Crea manifest.json (come text2sql — vedi dev/package_supx.py)
# remoteEntry hash da dist/

# 3. Zip
zip chartgen-0.1.0.supx manifest.json \
  frontend/dist/remoteEntry.*.js \
  frontend/dist/*.js \
  backend/src/bi_ai/chartgen/*.py

# 4. Copia in apache-superset extensions dir (bind-mounted)
cp chartgen-0.1.0.supx /path/to/apache-superset/docker/extensions/

# 5. Restart
docker compose -f /Users/tommasoelia/Git/apache-superset/docker-compose.yml restart superset
```

### 4.2 Creare `dev/package_supx.py` (utility script)
Script riutilizzabile che:
1. Legge `extension.json`
2. Trova l'hash del `remoteEntry` in `frontend/dist/`
3. Genera `manifest.json` nel formato corretto
4. Crea lo `.supx`

---

## Phase 5: Verification

```bash
# 1. Extension si carica
node /Users/tommasoelia/Git/bi-ai/test-extension.js
# Deve mostrare: "AI Chart panel visible: ✅ YES"

# 2. Suggest endpoint funziona
curl -X POST http://localhost:8088/extensions/bi-ai/chartgen/suggest ...
# Deve tornare viz_type valido

# 3. Create endpoint funziona  
curl -X POST http://localhost:8088/extensions/bi-ai/chartgen/create ...
# Deve tornare explore_url

# 4. Test E2E manuale
# Login → SQL Lab → seleziona KPI Data (goldlayer) → esegui query → 
# verifica "AI Chart" panel → verifica suggestion → click "Create Chart" →
# verifica navigazione a Explore con chart preconfigurato

# Anti-pattern checks
grep -r "viz_type" chartgen/backend/ | grep -v "echarts_timeseries_line\|echarts_bar\|pie\|table\|big_number_total"
# Nessun risultato = no viz_type inventati

grep -r "get_table_names\(\)" chartgen/
# Nessun risultato = nessuna introspection senza schema
```

---

## Note implementative

1. **LLM model:** Usare stesso client OpenRouter di text2sql (`llm.py`) — riusarlo dal package bi_ai.text2sql o copiarlo
2. **Reuse tenant:** `get_current_tenant_id()` da `bi_ai.text2sql.tenant` — importabile perché entrambi i backend sono nel container
3. **Virtual dataset naming:** Usare timestamp + hash del SQL per evitare collisioni di nome
4. **Schema nel dataset:** Settare `schema="goldlayer"` nel SqlaTable se il SQL usa viste goldlayer
5. **Owner:** Prendere da `flask_login.current_user.id`
6. **Explore URL:** `/explore/?slice_id={id}` apre direttamente il chart in edit mode

---

## Mapping prod vs dev

| Componente | Dev | Prod |
|---|---|---|
| chart_builder.py | ORM diretto (SqlaTable, Slice) | Identico |
| Virtual dataset | Creato al volo, non persistente | Potrebbe voler essere persistente con nome descrittivo |
| Explore navigation | `window.open(explore_url)` | Identico |
| Auth | `@protect()` → Superset session | Identico |
