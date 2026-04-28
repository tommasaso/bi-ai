import re
import sqlglot
from dataclasses import dataclass, field
from app.metadata import get_schema_metadata

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "MERGE", "REPLACE", "ATTACH", "DETACH",
}


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_sql: str = ""


def validate_sql(sql: str, allowed_tables: set[str] | None = None) -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(is_valid=False, errors=["SQL is empty."])

    stripped = sql.strip()

    # Check for multiple statements
    statements = [s.strip() for s in stripped.split(";") if s.strip()]
    if len(statements) > 1:
        return ValidationResult(
            is_valid=False,
            errors=["Multiple SQL statements are not allowed. Only a single SELECT or WITH query is permitted."],
        )

    # Remove trailing semicolons for further checks
    clean_sql = statements[0] if statements else stripped

    # Check it starts with SELECT or WITH
    upper = clean_sql.upper().lstrip()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return ValidationResult(
            is_valid=False,
            errors=["Only SELECT or WITH (CTE) queries are allowed."],
        )

    # Check for forbidden keywords
    tokens = re.findall(r"\b([A-Z_]+)\b", clean_sql.upper())
    found_forbidden = [kw for kw in tokens if kw in FORBIDDEN_KEYWORDS]
    if found_forbidden:
        return ValidationResult(
            is_valid=False,
            errors=[f"Forbidden SQL keyword(s) detected: {', '.join(set(found_forbidden))}."],
        )

    # Parse with sqlglot
    errors = []
    warnings = []
    normalized = clean_sql

    try:
        parsed = sqlglot.parse_one(clean_sql, dialect="sqlite")
        normalized = parsed.sql(dialect="sqlite")

        # Extract referenced tables
        if allowed_tables is None:
            schema = get_schema_metadata()
            allowed_tables = set(schema.keys())

        referenced_tables = set()
        for table in parsed.find_all(sqlglot.exp.Table):
            if table.name:
                referenced_tables.add(table.name.lower())

        unknown_tables = referenced_tables - {t.lower() for t in allowed_tables}
        if unknown_tables:
            errors.append(f"Query references unknown table(s): {', '.join(unknown_tables)}.")

        # Check for LIMIT
        has_limit = parsed.find(sqlglot.exp.Limit) is not None
        if not has_limit:
            warnings.append("Query does not have a LIMIT clause. Consider adding LIMIT 100 to avoid large result sets.")

    except sqlglot.errors.SqlglotError as e:
        errors.append(f"SQL parse error: {str(e)}")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        normalized_sql=normalized,
    )
