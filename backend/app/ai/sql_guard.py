"""
Safe Text-to-SQL enforcement layer (section 11).

Flow: LLM generates SQL -> validate_sql() -> execute_safe_sql() on the
READ-ONLY MySQL connection (a different DB user than the app itself uses,
granted SELECT-only at the database level — see docker/mysql/init and
docs/security.md). This module is the app-level half of that defense in
depth: even though the DB user physically cannot run DDL/DML, we still
parse and reject anything that isn't a single, simple SELECT against an
explicit table/column allowlist, before it ever reaches the connection.

Never call app.core.database.SessionLocal (the read-write session) from
here. Only ReadOnlySessionLocal / readonly_engine.
"""

import re

import sqlglot
from sqlglot import exp

from app.core.config import get_settings

settings = get_settings()

# --- Table allowlist: only analytics-safe, non-PII tables. Deliberately
# excludes users, audit_logs, ai_conversations, ai_messages. ---
ALLOWED_TABLES = {
    "shipments", "orders", "products", "customers", "suppliers",
    "supplier_metrics", "alerts", "root_causes", "recommendations",
    "shipment_predictions", "shipment_risk_factors", "model_versions",
}

# --- Column allowlist per table: blocks PII-adjacent columns even on an
# otherwise-allowed table (e.g. customers.city is fine, no email/street). ---
BLOCKED_COLUMNS = {
    "customers": {"street"},
}

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "rename", "call", "merge", "replace", "execute",
    "load_file", "into outfile", "into dumpfile", "lock", "unlock",
}

DEFAULT_ROW_LIMIT = settings.ai_sql_row_limit


class SQLValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _check_forbidden_keywords(sql: str) -> None:
    lowered = sql.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            raise SQLValidationError("FORBIDDEN_KEYWORD", f"Query contains a forbidden keyword: '{kw}'")


def _check_single_statement(sql: str) -> exp.Expression:
    statements = sqlglot.parse(sql, read="mysql")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError("MULTIPLE_STATEMENTS", "Only a single SQL statement is allowed")
    return statements[0]


def _check_select_only(tree: exp.Expression) -> None:
    if not isinstance(tree, exp.Select):
        raise SQLValidationError("NOT_A_SELECT", "Only SELECT statements are allowed")
    # Reject CTEs/subqueries that themselves contain non-select DML — sqlglot
    # would already fail to parse most of these as a Select root, but this
    # guards against parser edge cases.
    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
            raise SQLValidationError("EMBEDDED_DML", "Embedded DML/DDL detected inside the query")


def _check_table_allowlist(tree: exp.Expression) -> set[str]:
    tables = {t.name.lower() for t in tree.find_all(exp.Table)}
    disallowed = tables - ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(
            "TABLE_NOT_ALLOWED", f"Query references non-allowlisted table(s): {sorted(disallowed)}"
        )
    return tables


def _check_column_blocklist(tree: exp.Expression, tables: set[str]) -> None:
    for table in tables:
        blocked = BLOCKED_COLUMNS.get(table, set())
        if not blocked:
            continue
        for col in tree.find_all(exp.Column):
            if col.name.lower() in blocked:
                raise SQLValidationError(
                    "COLUMN_NOT_ALLOWED", f"Column '{col.name}' is not allowed in generated queries"
                )


def _enforce_row_limit(tree: exp.Select, max_rows: int) -> str:
    existing_limit = tree.args.get("limit")
    if existing_limit is not None:
        try:
            requested = int(existing_limit.expression.this)
        except (AttributeError, ValueError, TypeError):
            requested = max_rows
        if requested > max_rows:
            tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    else:
        tree = tree.limit(max_rows)
    return tree.sql(dialect="mysql")


def validate_sql(sql: str, max_rows: int = DEFAULT_ROW_LIMIT) -> str:
    """Raises SQLValidationError on anything unsafe. Returns a rewritten,
    row-limited SQL string safe to execute on the read-only connection."""
    if not sql or not sql.strip():
        raise SQLValidationError("EMPTY_QUERY", "Empty query")

    _check_forbidden_keywords(sql)
    tree = _check_single_statement(sql)
    _check_select_only(tree)
    tables = _check_table_allowlist(tree)
    _check_column_blocklist(tree, tables)
    return _enforce_row_limit(tree, max_rows)


def execute_safe_sql(db, sql: str) -> list[dict]:
    """db must be a Session bound to the READ-ONLY engine
    (app.core.database.ReadOnlySessionLocal). Applies both the app-level
    validation above AND a server-side execution-time cap."""
    from sqlalchemy import text

    safe_sql = validate_sql(sql)
    timeout_ms = settings.ai_sql_timeout_seconds * 1000
    db.execute(text(f"SET SESSION MAX_EXECUTION_TIME={timeout_ms}"))
    result = db.execute(text(safe_sql))
    columns = list(result.keys())
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return rows
