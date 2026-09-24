"""
Unit tests for the safe text-to-SQL layer (app/ai/sql_guard.py). No database
required — validate_sql() is pure parsing/validation.
"""

import pytest

from app.ai.sql_guard import SQLValidationError, validate_sql


def test_allows_simple_select_on_allowlisted_table():
    sql = "SELECT shipment_code, risk_score FROM shipments WHERE risk_level = 'CRITICAL'"
    result = validate_sql(sql)
    assert "shipments" in result
    assert "LIMIT" in result.upper()


def test_rejects_disallowed_table():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("SELECT * FROM users")
    assert exc.value.code == "TABLE_NOT_ALLOWED"


def test_rejects_multiple_statements_stacked_injection():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("SELECT * FROM shipments; DROP TABLE shipments;")
    assert exc.value.code == "FORBIDDEN_KEYWORD"


def test_rejects_delete():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("DELETE FROM shipments")
    assert exc.value.code == "FORBIDDEN_KEYWORD"


def test_rejects_update():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("UPDATE shipments SET risk_score = 0")
    assert exc.value.code == "FORBIDDEN_KEYWORD"


def test_rejects_blocked_column_even_on_allowed_table():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("SELECT street FROM customers")
    assert exc.value.code == "COLUMN_NOT_ALLOWED"


def test_enforces_row_limit_cap():
    result = validate_sql("SELECT supplier_name FROM suppliers ORDER BY risk_score DESC LIMIT 100000", max_rows=500)
    assert "LIMIT 500" in result.upper()


def test_injects_limit_when_missing():
    result = validate_sql("SELECT supplier_name FROM suppliers")
    assert "LIMIT" in result.upper()


def test_rejects_empty_query():
    with pytest.raises(SQLValidationError) as exc:
        validate_sql("")
    assert exc.value.code == "EMPTY_QUERY"


def test_rejects_non_select_root_statement():
    with pytest.raises(SQLValidationError):
        validate_sql("CREATE TABLE evil (id INT)")
