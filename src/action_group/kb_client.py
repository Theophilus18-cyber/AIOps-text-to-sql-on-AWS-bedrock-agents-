"""Bedrock Knowledge Base retrieval for the action-group Lambda."""

from __future__ import annotations

from typing import Any

import src.common.aws as aws
import src.common.config as config


class KbError(RuntimeError):
    pass


def retrieve(question: str, top_k: int = 5) -> list[str]:
    if not config.KB_ID:
        raise KbError("KB_ID is not configured.")

    client = aws.bedrock_agent_runtime()
    response = client.retrieve(
        knowledgeBaseId=config.KB_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": top_k,
                # Schema docs are stored whole (chunking disabled) so we want
                # the full text of each retrieved document.
            }
        },
    )

    texts: list[str] = []
    for item in response.get("retrievalResults", []):
        content = item.get("content", {})
        text = content.get("text") or _flatten_content(content)
        if text:
            texts.append(text)
    return texts


def _flatten_content(content: dict[str, Any]) -> str:
    """Best-effort extraction when a result arrives as nested content blocks."""
    parts: list[str] = []
    for key in ("text", "markdown"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    if parts:
        return "\n".join(parts)
    return str(content.get("text", ""))
