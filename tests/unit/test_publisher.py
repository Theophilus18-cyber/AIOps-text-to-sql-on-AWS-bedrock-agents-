"""Tests for the S3 + ingestion publisher."""

from __future__ import annotations

from unittest import mock

import src.common.aws as aws
import src.common.config as config
from src.doc_builder.publisher import publish


def test_publish_uploads_and_starts_ingestion(monkeypatch) -> None:
    monkeypatch.setattr(config, "DOCS_BUCKET", "docs-bucket")
    monkeypatch.setattr(config, "DOCS_PREFIX", "schema-docs/approved/")
    monkeypatch.setattr(config, "KB_ID", "kb-123")
    monkeypatch.setattr(config, "DATA_SOURCE_ID", "ds-456")

    mock_s3 = mock.Mock()
    mock_bedrock = mock.Mock()
    mock_bedrock.start_ingestion_job.return_value = {"ingestionJob": {"ingestionJobId": "job-1"}}

    monkeypatch.setattr(aws, "s3", lambda: mock_s3)
    monkeypatch.setattr(aws, "bedrock_agent", lambda: mock_bedrock)

    summary = publish({"my_table": "# Table\n\ndescription\n"}, replace=False)

    assert summary["ingestion_job_id"] == "job-1"
    assert mock_s3.put_object.call_args.kwargs["Key"] == "schema-docs/approved/my_table.md"
    assert mock_bedrock.start_ingestion_job.call_args.kwargs["knowledgeBaseId"] == "kb-123"


def test_publish_prunes_stale_when_replace(monkeypatch) -> None:
    monkeypatch.setattr(config, "DOCS_BUCKET", "docs-bucket")
    monkeypatch.setattr(config, "DOCS_PREFIX", "schema-docs/approved/")
    monkeypatch.setattr(config, "KB_ID", "kb-123")
    monkeypatch.setattr(config, "DATA_SOURCE_ID", "ds-456")

    mock_s3 = mock.Mock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "schema-docs/approved/keep.md"},
            {"Key": "schema-docs/approved/stale.md"},
        ]
    }
    mock_bedrock = mock.Mock()
    mock_bedrock.start_ingestion_job.return_value = {"ingestionJob": {"ingestionJobId": "job-2"}}

    monkeypatch.setattr(aws, "s3", lambda: mock_s3)
    monkeypatch.setattr(aws, "bedrock_agent", lambda: mock_bedrock)

    publish({"keep": "# doc"}, replace=True)

    deleted_keys = [call.kwargs["Key"] for call in mock_s3.delete_object.call_args_list]
    assert "schema-docs/approved/stale.md" in deleted_keys
    assert "schema-docs/approved/keep.md" not in deleted_keys
