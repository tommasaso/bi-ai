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


def ensure_tenant_filter(sql: str, tenant_id: int) -> str:
    """Inject WHERE tenant_id = <tenant_id> into every SELECT if missing."""
    import sqlglot.expressions as exp

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
        for select_node in tree.find_all(exp.Select):
            tenant_cond = exp.EQ(
                this=exp.Column(this=exp.Identifier(this="tenant_id")),
                expression=exp.Literal.number(tenant_id),
            )
            where = select_node.args.get("where")
            if where is None:
                select_node.set("where", exp.Where(this=tenant_cond))
            else:
                already = any(
                    isinstance(col, exp.Column) and col.name.lower() == "tenant_id"
                    for col in where.find_all(exp.Column)
                )
                if not already:
                    select_node.set("where", exp.Where(
                        this=exp.And(this=tenant_cond, expression=where.this)
                    ))
        return tree.sql(dialect="postgres")
    except Exception:
        normalized = sql.rstrip().rstrip(";")
        if "tenant_id" not in normalized.lower():
            if re.search(r"\bwhere\b", normalized, re.IGNORECASE):
                normalized = re.sub(
                    r"\bwhere\b",
                    f"WHERE tenant_id = {tenant_id} AND ",
                    normalized,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                normalized = f"{normalized} WHERE tenant_id = {tenant_id}"
        return normalized


def validate_sql(sql: str, allowed_tables: set[str] | None = None, dialect: str = "sqlite", tenant_id: int | None = None) -> ValidationResult:
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

        if tenant_id is not None:
            normalized = ensure_tenant_filter(normalized, tenant_id)

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
