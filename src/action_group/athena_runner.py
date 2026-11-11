"""Athena execution for the action-group Lambda.

Runs validated SQL on the enforced workgroup, waits for completion, and
returns a capped, serialisable result set.  The row and per-cell caps keep a
single agent turn from flooding the model context or the Lambda response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import src.common.aws as aws
import src.common.config as config
from src.common.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    execution_id: str
    runtime_ms: int


class AthenaError(RuntimeError):
    pass


def run_sql(sql: str) -> QueryResult:
    client = aws.athena()
    output_location = _output_location()

    start = client.start_query_execution(
        QueryString=sql,
        WorkGroup=config.ATHENA_WORKGROUP,
        ResultConfiguration={"OutputLocation": output_location},
    )
    execution_id = start["QueryExecutionId"]

    started_at = datetime.now(UTC)
    try:
        state, state_reason = _wait(client, execution_id)
    except AthenaError:
        raise
    runtime_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)

    if state != "SUCCEEDED":
        raise AthenaError(f"Athena query failed ({state}): {state_reason or 'unknown error'}")

    columns, rows = _fetch(client, execution_id)
    total = len(rows)

    truncated = total > config.MAX_ROWS
    if truncated:
        rows = rows[: config.MAX_ROWS]

    # Defensive cell truncation so a single wide string cannot blow the payload.
    rows = [_truncate_cells(row) for row in rows]

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        execution_id=execution_id,
        runtime_ms=runtime_ms,
    )


def _output_location() -> str:
    if not config.ATHENA_RESULTS_BUCKET:
        raise AthenaError("ATHENA_RESULTS_BUCKET is not configured.")
    prefix = config.ATHENA_RESULTS_PREFIX.strip("/")
    return f"s3://{config.ATHENA_RESULTS_BUCKET}/{prefix}/"


def _wait(client: Any, execution_id: str) -> tuple[str, str]:
    import time

    deadline = time.monotonic() + 30.0
    while True:
        status = client.get_query_execution(QueryExecutionId=execution_id)
        execution = status["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            reason = execution["Status"].get("StateChangeReason", "")
            return state, reason
        if time.monotonic() > deadline:
            client.stop_query_execution(QueryExecutionId=execution_id)
            raise AthenaError("Athena query timed out after 30s.")
        time.sleep(0.25)


def _fetch(client: Any, execution_id: str) -> tuple[tuple[str, ...], list[list[Any]]]:
    columns: list[str] = []
    rows: list[list[Any]] = []
    token: str | None = None

    while True:
        kwargs: dict[str, Any] = {
            "QueryExecutionId": execution_id,
            "MaxResults": 1000,
        }
        if token:
            kwargs["NextToken"] = token

        result = client.get_query_results(**kwargs)
        result_set = result["ResultSet"]

        if not columns and result_set.get("Rows"):
            header = result_set["Rows"][0].get("Data", [])
            columns = [_cell_text(cell) for cell in header]

        for row in result_set.get("Rows", [])[1:]:
            rows.append([_cell_value(cell) for cell in row.get("Data", [])])

        token = result.get("NextToken")
        if token is None or len(rows) >= config.MAX_ROWS:
            break

    return tuple(columns), rows


def _cell_text(cell: dict[str, Any]) -> str:
    return str(cell.get("VarCharValue", ""))


def _cell_value(cell: dict[str, Any]) -> Any:
    return cell.get("VarCharValue")


def _truncate_cells(row: list[Any]) -> list[Any]:
    return [
        (value[: config.MAX_CELL_CHARS] + "…")
        if isinstance(value, str) and len(value) > config.MAX_CELL_CHARS
        else value
        for value in row
    ]


def to_dict(result: QueryResult) -> dict[str, Any]:
    return {
        "columns": list(result.columns),
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_id": result.execution_id,
        "runtime_ms": result.runtime_ms,
    }
