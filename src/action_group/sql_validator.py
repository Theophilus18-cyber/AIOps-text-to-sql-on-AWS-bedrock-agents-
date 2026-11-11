"""SQL validation for the action-group Lambda.

This is the security-critical layer.  The agent's generated SQL is untrusted
input and must be rejected unless it is exactly one read-only SELECT that:

* is within the configured length limit,
* parses cleanly under sqlglot's Trino dialect (comments are ignored by the
  parser, so a keyword buried in a comment cannot smuggle in a statement),
* is a SELECT or a UNION of SELECTs (any DML/DDL — INSERT, DELETE, CREATE,
  DROP, EXPLAIN, SET, ... — parses to a different node type and is rejected),
* touches only tables on the allow-list (never the Athena results table or a
  CTE name),
* has an explicit LIMIT at or below the configured cap — or is a single-row
  aggregate (e.g. ``SELECT count(*) ...``) which returns one row by nature.

The default deny posture matters more than the diagnostics: any parse failure
or unexpected shape is rejected rather than passed through to Athena.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    table_names: tuple[str, ...] = field(default_factory=tuple)


class SqlValidator:
    """Validates agent-generated SQL against a static allow-list."""

    dialect = "trino"

    def __init__(
        self,
        allowed_tables: set[str] | list[str] | tuple[str, ...],
        max_query_length: int = 8192,
        max_limit: int = 1000,
    ) -> None:
        self.allowed_tables = {t.lower() for t in allowed_tables}
        self.max_query_length = max_query_length
        self.max_limit = max_limit

    def validate(self, sql: str) -> ValidationResult:
        if not isinstance(sql, str) or not sql.strip():
            return ValidationResult(False, "SQL is empty.")

        if len(sql) > self.max_query_length:
            return ValidationResult(
                False, f"SQL is {len(sql)} chars; limit is {self.max_query_length}."
            )

        try:
            expressions = sqlglot.parse(sql, read=self.dialect)
        except (ParseError, TokenError) as exc:
            return ValidationResult(False, f"SQL parse error: {exc}")

        # sqlglot emits None for comment-only fragments; drop them so a trailing
        # comment is harmless while a real second statement still counts.
        statements = [e for e in expressions if e is not None]
        if not statements:
            return ValidationResult(False, "SQL contains only comments.")
        if len(statements) != 1:
            return ValidationResult(False, "Exactly one statement is allowed.")

        expression = statements[0]
        if not isinstance(expression, (exp.Select, exp.Union)):
            return ValidationResult(False, "Top-level statement must be a SELECT.")

        cte_names = _cte_names(expression)
        table_names = _table_names(expression)

        unknown = sorted(
            name
            for name in table_names
            if name not in cte_names and name not in self.allowed_tables
        )
        if unknown:
            return ValidationResult(False, f"References unknown table(s): {', '.join(unknown)}.")

        if not _has_valid_limit(expression, self.max_limit):
            return ValidationResult(
                False,
                f"Add an explicit LIMIT of at most {self.max_limit} "
                "(aggregate single-row queries are exempt).",
            )

        return ValidationResult(True, table_names=tuple(sorted(table_names)))


def _cte_names(expression: exp.Expression) -> set[str]:
    # The WITH clause is stored under "with_" in current sqlglot; accept the
    # plain "with" spelling too for forward/backward compatibility.
    with_clause = expression.args.get("with_") or expression.args.get("with")
    names: set[str] = set()
    if with_clause is None:
        return names
    for cte in with_clause.expressions:
        alias = cte.alias_or_name
        if alias:
            names.add(alias.lower())
    return names


def _table_names(expression: exp.Expression) -> set[str]:
    names: set[str] = set()
    for table in expression.find_all(exp.Table):
        name = table.name
        if name:
            names.add(name.lower())
    return names


def _has_valid_limit(expression: exp.Expression, max_limit: int) -> bool:
    if _is_single_row_aggregate(expression):
        return True

    limit = expression.args.get("limit")
    if limit is None:
        return False
    # `LIMIT n` is an exp.Limit with an integer-ish expression child.
    value = limit.expression
    if value is None:
        return False
    try:
        n = int(value.name)
    except (ValueError, AttributeError):
        return False
    return 1 <= n <= max_limit


def _is_single_row_aggregate(expression: exp.Expression) -> bool:
    """True when the SELECT produces exactly one row without a LIMIT.

    Heuristic: no GROUP BY / HAVING and every selected expression is an
    aggregate function (count, sum, avg, min, max, approx_distinct, ...).
    Aliases (``sum(amt) AS total``) are unwrapped before the check.
    """
    if isinstance(expression, exp.Union):
        return False
    select = cast(exp.Select, expression)
    if select.args.get("group") is not None or select.args.get("having") is not None:
        return False

    projections = list(select.selects)
    if not projections:
        return False
    # An aliased aggregate (`sum(amt) AS total`) parses as an Alias wrapping an
    # AggFunc, so unwrap one level before the aggregate check.
    return all(
        isinstance(p, exp.AggFunc) or (isinstance(p, exp.Alias) and isinstance(p.this, exp.AggFunc))
        for p in projections
    )
