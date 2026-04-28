import re
import sqlglot
from dataclasses import dataclass, field

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


def validate_sql(sql: str, allowed_tables: set[str] | None = None, dialect: str = "sqlite") -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(is_valid=False, errors=["SQL is empty."])

    statements = [s.strip() for s in sql.strip().split(";") if s.strip()]
    if len(statements) > 1:
        return ValidationResult(
            is_valid=False,
            errors=["Multiple SQL statements are not allowed."],
        )

    clean_sql = statements[0]
    upper = clean_sql.upper().lstrip()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return ValidationResult(is_valid=False, errors=["Only SELECT or WITH queries are allowed."])

    tokens = re.findall(r"\b([A-Z_]+)\b", clean_sql.upper())
    found_forbidden = [kw for kw in tokens if kw in FORBIDDEN_KEYWORDS]
    if found_forbidden:
        return ValidationResult(
            is_valid=False,
            errors=[f"Forbidden SQL keyword(s): {', '.join(set(found_forbidden))}."],
        )

    errors: list[str] = []
    warnings: list[str] = []
    normalized = clean_sql

    try:
        parsed = sqlglot.parse_one(clean_sql, dialect=dialect)
        normalized = parsed.sql(dialect=dialect)

        if allowed_tables is not None:
            referenced = {t.name.lower() for t in parsed.find_all(sqlglot.exp.Table) if t.name}
            unknown = referenced - {t.lower() for t in allowed_tables}
            if unknown:
                errors.append(f"Query references unknown table(s): {', '.join(unknown)}.")

        if not parsed.find(sqlglot.exp.Limit):
            warnings.append("No LIMIT clause. Consider adding LIMIT 100.")

    except sqlglot.errors.SqlglotError as e:
        errors.append(f"SQL parse error: {str(e)}")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, normalized_sql=normalized)
