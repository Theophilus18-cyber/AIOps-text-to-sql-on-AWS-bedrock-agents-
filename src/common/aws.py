"""AWS SDK helpers with lazy boto3 import.

boto3 is not pinned in the Lambda `requirements.txt` because the managed
runtime already ships a compatible version; importing it only when a caller
actually needs it keeps the package importable in minimal test environments.
"""

from __future__ import annotations

from typing import Any

import src.common.config as config


def _client(service: str) -> Any:
    import boto3

    return boto3.client(service, region_name=config.REGION)


def athena() -> Any:
    return _client("athena")


def bedrock_agent_runtime() -> Any:
    return _client("bedrock-agent-runtime")


def bedrock_agent() -> Any:
    return _client("bedrock-agent")


def bedrock_runtime() -> Any:
    return _client("bedrock-runtime")


def bedrock() -> Any:
    return _client("bedrock")


def glue() -> Any:
    return _client("glue")


def s3() -> Any:
    return _client("s3")
