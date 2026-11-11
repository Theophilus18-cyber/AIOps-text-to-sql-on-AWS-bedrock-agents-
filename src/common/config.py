"""Environment-driven configuration.

Every knob is read from the process environment so that a single build of the
Lambda package behaves differently per deployment without code changes.  Local
scripts reuse the same helpers so behaviour stays consistent between local and
deployed runs.
"""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return default if raw is None or raw == "" else raw


REGION = _str("REGION", "us-east-1")
ATHENA_DATABASE = _str("ATHENA_DATABASE", "text2sql_dev_lake")
ATHENA_WORKGROUP = _str("ATHENA_WORKGROUP", "text2sql-dev")
ATHENA_RESULTS_BUCKET = _str("ATHENA_RESULTS_BUCKET", "")
ATHENA_RESULTS_PREFIX = _str("ATHENA_RESULTS_PREFIX", "athena-results")

KB_ID = _str("KB_ID", "")
DATA_SOURCE_ID = _str("DATA_SOURCE_ID", "")

DOCS_BUCKET = _str("DOCS_BUCKET", "")
DOCS_PREFIX = _str("DOCS_PREFIX", "schema-docs/approved/")
GLOSSARY_PREFIX = _str("GLOSSARY_PREFIX", "glossary/")
GLUE_DATABASE = _str("GLUE_DATABASE", ATHENA_DATABASE)

MAX_ROWS = _int("MAX_ROWS", 100)
MAX_CELL_CHARS = _int("MAX_CELL_CHARS", 500)
MAX_QUERY_LENGTH = _int("MAX_QUERY_LENGTH", 8192)
MAX_LIMIT = _int("MAX_LIMIT", 1000)

EMBEDDING_MODEL_ID = _str("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")

MODEL_ID = _str("MODEL_ID", "anthropic.claude-sonnet-5-5")
GUARDRAIL_ID = _str("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = _str("GUARDRAIL_VERSION", "")

LOG_LEVEL = _str("LOG_LEVEL", "INFO")
