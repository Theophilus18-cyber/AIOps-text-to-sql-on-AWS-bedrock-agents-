"""Writes rendered schema docs to S3 and triggers KB ingestion."""

from __future__ import annotations

from typing import Any

import src.common.aws as aws
import src.common.config as config
from src.common.logging_setup import get_logger

logger = get_logger(__name__)


class PublishError(RuntimeError):
    pass


def publish(documents: dict[str, str], replace: bool = False) -> dict[str, str]:
    """Upload rendered docs and start a KB ingestion job.

    ``documents`` maps table name -> Markdown text.  Returns a summary dict.
    """
    if not config.DOCS_BUCKET:
        raise PublishError("DOCS_BUCKET is not configured.")

    s3 = aws.s3()
    prefix = config.DOCS_PREFIX

    keys: list[str] = []
    for table_name, text in documents.items():
        key = f"{prefix}{table_name}.md"
        s3.put_object(Bucket=config.DOCS_BUCKET, Key=key, Body=text.encode("utf-8"))
        keys.append(key)
        logger.info("published doc", extra={"action": "publish_doc", "key": key})

    if replace:
        _prune_stale(s3, set(keys))

    ingestion_job_id = _start_ingestion()

    return {
        "published": keys,
        "ingestion_job_id": ingestion_job_id,
    }


def _prune_stale(s3: Any, keep: set[str]) -> None:
    """Remove documents under the approved prefix that were not just written.

    Ensures a table removed from the catalog does not linger in the KB.
    """
    response = s3.list_objects_v2(Bucket=config.DOCS_BUCKET, Prefix=config.DOCS_PREFIX)
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key not in keep and key.endswith(".md"):
            s3.delete_object(Bucket=config.DOCS_BUCKET, Key=key)
            logger.info("pruned stale doc", extra={"action": "prune_doc", "key": key})


def _start_ingestion() -> str:
    if not config.KB_ID or not config.DATA_SOURCE_ID:
        raise PublishError("KB_ID and DATA_SOURCE_ID are required for ingestion.")

    client = aws.bedrock_agent()
    response = client.start_ingestion_job(
        knowledgeBaseId=config.KB_ID,
        dataSourceId=config.DATA_SOURCE_ID,
    )
    job_id = response.get("ingestionJob", {}).get("ingestionJobId", "")
    logger.info("started ingestion", extra={"action": "start_ingestion", "job_id": job_id})
    return job_id
