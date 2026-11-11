"""Tool functions used by the orchestrator.

``get_schema_context`` pulls schema docs from the KB; ``run_sql`` validates SQL
and runs it on Athena. Both return JSON so the model can read a result or error.
"""

from __future__ import annotations

import json
import time
from typing import Any

import src.common.aws as aws
import src.common.config as config
from src.action_group import athena_runner, kb_client
from src.action_group.sql_validator import SqlValidator
from src.common.logging_setup import get_logger

logger = get_logger(__name__)

# Table allow-list is the current set of tables in Glue, refreshed every TTL.
_TABLE_TTL_SECONDS = 300.0

_table_names_cache: set[str] = set()
_table_names_fetched_at = 0.0


def get_schema_context(question: str) -> str:
    if not question.strip():
        return json.dumps({"error": "question is required."})
    try:
        texts = kb_client.retrieve(question.strip(), top_k=5)
    except kb_client.KbError as exc:
        return json.dumps({"error": str(exc)})
    if not texts:
        return json.dumps({"error": "no schema context found."})
    return json.dumps({"context": "\n\n---\n\n".join(texts)})


def run_sql(sql: str) -> str:
    result = _validator().validate(sql)
    if not result.ok:
        return json.dumps({"error": result.reason})
    try:
        query = athena_runner.run_sql(sql)
    except athena_runner.AthenaError as exc:
        return json.dumps({"error": str(exc)})
    payload = athena_runner.to_dict(query)
    payload["sql"] = sql
    return json.dumps(payload, default=str)


def _validator() -> SqlValidator:
    return SqlValidator(
        allowed_tables=_allowed_tables(),
        max_query_length=config.MAX_QUERY_LENGTH,
        max_limit=config.MAX_LIMIT,
    )


def _allowed_tables() -> set[str]:
    global _table_names_cache, _table_names_fetched_at
    now = time.monotonic()
    if _table_names_cache and now - _table_names_fetched_at < _TABLE_TTL_SECONDS:
        return _table_names_cache
    names = _list_glue_tables(config.GLUE_DATABASE)
    _table_names_fetched_at = now
    if names:
        _table_names_cache = names
    return _table_names_cache


def _list_glue_tables(database: str) -> set[str]:
    glue = aws.glue()
    names: set[str] = set()
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"DatabaseName": database}
        if token:
            kwargs["NextToken"] = token
        response = glue.get_tables(**kwargs)
        for table in response.get("TableList", []):
            name = table.get("Name")
            if name:
                names.add(name.lower())
        token = response.get("NextToken")
        if token is None:
            break
    return names
