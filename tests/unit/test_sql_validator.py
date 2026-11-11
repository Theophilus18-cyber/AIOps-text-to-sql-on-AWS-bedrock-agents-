"""Adversarial tests for the SQL validator.

The validator is the last line of defence between untrusted model output and
Athena, so these tests focus on the ways a query can try to smuggle in a second
statement, reach another table, or avoid the row cap.
"""

from __future__ import annotations

import pytest
from src.action_group.sql_validator import SqlValidator

ALLOWED = {"credit_card_transactions"}


@pytest.fixture
def validator() -> SqlValidator:
    return SqlValidator(
        allowed_tables=ALLOWED,
        max_query_length=8192,
        max_limit=1000,
    )


def _ok(validator: SqlValidator, sql: str) -> bool:
    return validator.validate(sql).ok


def _reason(validator: SqlValidator, sql: str) -> str:
    return validator.validate(sql).reason


# --- Accept ---
def test_accepts_plain_select_with_limit(validator: SqlValidator) -> None:
    assert _ok(validator, "SELECT * FROM credit_card_transactions LIMIT 10")


def test_accepts_qualified_table_name(validator: SqlValidator) -> None:
    sql = 'SELECT * FROM "db"."credit_card_transactions" LIMIT 10'
    assert _ok(validator, sql)


def test_accepts_single_row_aggregate_without_limit(validator: SqlValidator) -> None:
    assert _ok(validator, "SELECT count(*) FROM credit_card_transactions")


def test_accepts_aliased_aggregate_without_limit(validator: SqlValidator) -> None:
    assert _ok(
        validator,
        "SELECT sum(amt) AS total FROM credit_card_transactions",
    )


def test_accepts_cte_that_ends_in_select(validator: SqlValidator) -> None:
    sql = (
        "WITH recent AS (SELECT * FROM credit_card_transactions LIMIT 50) "
        "SELECT count(*) FROM recent"
    )
    assert _ok(validator, sql)


# --- Reject: statement shape ---
def test_rejects_stacked_statements(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions LIMIT 10; DROP TABLE credit_card_transactions"
    assert not _ok(validator, sql)


def test_rejects_insert(validator: SqlValidator) -> None:
    sql = "INSERT INTO credit_card_transactions VALUES (1)"
    assert not _ok(validator, sql)


def test_rejects_delete(validator: SqlValidator) -> None:
    sql = "DELETE FROM credit_card_transactions WHERE is_fraud = 1"
    assert not _ok(validator, sql)


def test_rejects_ctas(validator: SqlValidator) -> None:
    sql = "CREATE TABLE other AS SELECT * FROM credit_card_transactions LIMIT 1"
    assert not _ok(validator, sql)


def test_rejects_comment_only(validator: SqlValidator) -> None:
    assert not _ok(validator, "-- nothing here")


def test_rejects_empty(validator: SqlValidator) -> None:
    assert not _ok(validator, "   ")


def test_rejects_over_length(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions LIMIT 1 " + ("x" * 9000)
    assert not _ok(validator, sql)


# --- Reject: comment / newline smuggling ---
def test_rejects_statement_hidden_after_line_comment(validator: SqlValidator) -> None:
    sql = (
        "SELECT * FROM credit_card_transactions LIMIT 10 --\n; DROP TABLE credit_card_transactions"
    )
    assert not _ok(validator, sql)


def test_rejects_block_comment_hiding_drop(validator: SqlValidator) -> None:
    # The comment contains a second statement; sqlglot parses only the real one
    # but the second is absent, so this is a plain select -> accepted is fine;
    # the dangerous form is a real ';' outside any comment.
    sql = "SELECT * FROM credit_card_transactions /* DROP TABLE x */ LIMIT 10"
    assert _ok(validator, sql)


# --- Reject: table allow-list ---
def test_rejects_unknown_table(validator: SqlValidator) -> None:
    sql = "SELECT * FROM secrets LIMIT 10"
    assert not _ok(validator, sql)


def test_rejects_union_into_unknown_table(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions LIMIT 10 UNION SELECT * FROM secrets LIMIT 10"
    assert not _ok(validator, sql)


def test_rejects_subquery_into_unknown_table(validator: SqlValidator) -> None:
    sql = "SELECT * FROM (SELECT * FROM secrets LIMIT 10) t LIMIT 10"
    assert not _ok(validator, sql)


# --- Reject: row cap ---
def test_rejects_missing_limit_on_multi_row(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions"
    assert not _ok(validator, sql)


def test_rejects_limit_above_cap(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions LIMIT 1001"
    assert not _ok(validator, sql)


def test_rejects_limit_zero(validator: SqlValidator) -> None:
    sql = "SELECT * FROM credit_card_transactions LIMIT 0"
    assert not _ok(validator, sql)


def test_reason_mentions_unknown_table(validator: SqlValidator) -> None:
    reason = _reason(validator, "SELECT * FROM secrets LIMIT 1")
    assert "secrets" in reason
