"""Lambda entry point for the doc-builder.

Two modes, selected by the event:

* ``{"mode": "build"}`` (default) — reads the glossary from S3, extracts table
  metadata from Glue, renders docs, publishes them, and starts ingestion.
* ``{"mode": "list_tables"}`` — returns the tables visible in the catalog, for
  smoke-testing the extractor during the refresh pipeline.

The function is also invoked directly by ``scripts/refresh.py`` with an S3
event payload; in that case the payload is ignored and a full build runs.
"""

from __future__ import annotations

from typing import Any

import src.common.aws as aws
import src.common.config as config
from src.common.logging_setup import get_logger, setup
from src.doc_builder.extractors.glue import GlueExtractor
from src.doc_builder.publisher import publish
from src.doc_builder.renderer import render_table_doc

setup(config.LOG_LEVEL)
logger = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    mode = event.get("mode", "build")

    try:
        if mode == "list_tables":
            return {"tables": GlueExtractor().list_tables(config.GLUE_DATABASE)}

        glossary = _load_glossary()
        extractor = GlueExtractor()
        tables = extractor.list_tables(config.GLUE_DATABASE)

        documents: dict[str, str] = {}
        for name in tables:
            table_doc = extractor.get_table(config.GLUE_DATABASE, name)
            documents[name] = render_table_doc(table_doc, glossary)

        summary = publish(documents, replace=True)
        return {"mode": "build", **summary}
    except Exception as exc:
        logger.exception("doc build failed")
        return {"error": str(exc)}


def _load_glossary() -> dict[str, Any]:
    """Load and merge every glossary YAML from the docs bucket.

    Each ``glossary/*.yaml`` file maps table name -> glossary entry.  Loading
    every file under the glossary prefix lets a new dataset contribute its own
    business definitions without code changes.  Falls back to a bundled glossary
    when S3 is unavailable (e.g. local tests) so the builder still works.
    """
    import yaml

    merged: dict[str, Any] = {}
    if config.DOCS_BUCKET:
        try:
            s3 = aws.s3()
            for page in s3.get_paginator("list_objects_v2").paginate(
                Bucket=config.DOCS_BUCKET, Prefix=config.GLOSSARY_PREFIX
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith((".yaml", ".yml")):
                        continue
                    body = s3.get_object(Bucket=config.DOCS_BUCKET, Key=key)["Body"].read()
                    data = yaml.safe_load(body.decode("utf-8"))
                    if isinstance(data, dict):
                        merged.update(data)
        except Exception as exc:
            logger.warning("glossary load failed, continuing with fallback: %s", exc)

    return merged or _bundled_glossary()


def _bundled_glossary() -> dict[str, Any]:
    """Fallback glossary embedded in the package for local/dev runs.

    The canonical source is ``glossary/credit_card_transactions.yaml``; this
    copy is only a resilience fallback and must not diverge.
    """
    import yaml

    text = """
credit_card_transactions:
  description: "Credit card transactions with merchant, cardholder, location and fraud labels."
  business_meaning: "Each row is one credit card transaction from 2019-01 through 2020-06."
  metrics:
    - "Total spend = sum(amt)"
    - "Fraud rate = avg(is_fraud)"
    - "Transactions per category = count(*) grouped by category"
  code_values:
    is_fraud: "0 = not fraud, 1 = fraud"
  join_keys:
    - "cc_num is a card number used to join a card's transactions; never expose it."
"""
    return yaml.safe_load(text) or {}
