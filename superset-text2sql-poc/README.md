# Superset Text-to-SQL PoC

A local Proof of Concept demonstrating AI-assisted SQL generation for Apache Superset SQL Lab.

Users write a natural language question. The system discovers available metadata, calls an LLM via OpenRouter, validates the generated SQL, and presents it for manual copy-paste into Superset SQL Lab.

```
User question → metadata discovery → LLM text-to-SQL → SQL validation → query preview → manual copy to Superset SQL Lab
```

**The generated SQL is never executed automatically. Final execution is always under user control.**

---

## Quickstart

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set LLM_API_KEY
python -m app.seed_demo_data
streamlit run app/ui.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set LLM_API_KEY
python -m app.seed_demo_data
streamlit run app/ui.py
```

---

## Configuration

Copy `.env.example` to `.env` and set your values:

```env
LLM_API_KEY=your_openrouter_api_key_here
LLM_MODEL=qwen/qwen3.5-coder
```

### Get an OpenRouter API Key

1. Go to https://openrouter.ai
2. Create an account
3. Navigate to Keys and create a new API key
4. Paste it into `.env` as `LLM_API_KEY`

### Supported Models

```env
LLM_MODEL=qwen/qwen3.5-coder
```
```env
LLM_MODEL=anthropic/claude-sonnet-4-5
```
```env
LLM_MODEL=openai/gpt-4.1-mini
```
```env
LLM_MODEL=google/gemini-2.5-flash
```

---

## Example Questions

```
Show me the top 10 lines with the highest average delay in the last 30 days.
```
```
Calculate punctuality rate by line for the current month.
```
```
Show daily passenger count trend for the last 60 days.
```
```
List vehicles with the highest number of critical anomalies.
```
```
Compare average delay between bus and tram lines.
```
```
Show the number of diagnostic alarms by severity in the last 30 days.
```
```
Compare passenger boardings by transport mode for the last 60 days.
```

---

## Expected Output Example

**Question:** Show me the top 10 lines with the highest average delay in the last 30 days.

**Generated SQL:**
```sql
SELECT
    l.line_id,
    l.line_name,
    AVG(se.arrival_delay_seconds) AS average_delay_seconds
FROM stop_events se
JOIN lines l ON se.line_id = l.line_id
WHERE se.service_date >= DATE('now', '-30 days')
GROUP BY l.line_id, l.line_name
ORDER BY average_delay_seconds DESC
LIMIT 10;
```

**Explanation:** Calculates the average arrival delay for each line over the last 30 days and returns the 10 lines with the highest average delay.

**Used tables:** stop_events, lines

---

## Using the Query in Superset SQL Lab

1. Generate the query in this PoC.
2. Click to copy or manually select the SQL.
3. Open Apache Superset → SQL Lab.
4. Select the appropriate database connection.
5. Paste the query.
6. Review it carefully.
7. Click Run.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Architecture

| Component | Responsibility |
|-----------|---------------|
| `app/config.py` | Reads `.env`, validates required settings |
| `app/database.py` | SQLAlchemy engine and inspector |
| `app/seed_demo_data.py` | Creates and populates demo SQLite database |
| `app/metadata.py` | Reads schema and builds metadata context |
| `app/metrics_catalog.py` | Loads certified metrics from YAML |
| `app/prompt_builder.py` | Builds system and user prompts |
| `app/llm_client.py` | Calls OpenRouter via OpenAI SDK |
| `app/sql_validator.py` | Validates generated SQL with sqlglot |
| `app/ui.py` | Streamlit UI |
| `data/metrics_catalog.yaml` | Certified metric definitions |

---

## Future Extensions

- Direct Superset SQL Lab integration via URL parameters
- Superset API integration for automatic chart generation
- Real Superset dataset and metric awareness
- Semantic layer / RBAC integration
- Query logging and text-to-SQL accuracy evaluation
