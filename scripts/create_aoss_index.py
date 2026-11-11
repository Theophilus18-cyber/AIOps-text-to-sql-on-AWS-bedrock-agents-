"""Create the vector index Bedrock KB expects in an OpenSearch Serverless collection.

Bedrock KB does not create the index itself when you bring your own collection,
so this runs before the knowledge base. Idempotent: an existing index is treated
as success. Uses the ambient AWS credentials (the same profile terraform runs
with), which must be a principal in the collection's data access policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

VECTOR_FIELD = "bedrock-knowledge-base-default-vector"
TEXT_FIELD = "AMAZON_BEDROCK_TEXT_CHUNK"
METADATA_FIELD = "AMAZON_BEDROCK_METADATA"


def _body(dimension: int) -> bytes:
    return json.dumps(
        {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    VECTOR_FIELD: {
                        "type": "knn_vector",
                        "dimension": dimension,
                        "method": {"name": "hnsw", "engine": "faiss"},
                    },
                    TEXT_FIELD: {"type": "text"},
                    METADATA_FIELD: {"type": "text"},
                }
            },
        }
    ).encode("utf-8")


def _url(endpoint: str, index: str) -> str:
    base = endpoint if endpoint.startswith(("http://", "https://")) else f"https://{endpoint}"
    return f"{base.rstrip('/')}/{index}"


def _send(credentials, region: str, method: str, url: str, data: bytes) -> tuple[int, str]:
    request = AWSRequest(
        method=method,
        url=url,
        data=data,
        headers={
            "Content-Type": "application/json",
            # AOSS rejects signatures that omit the payload hash; set it explicitly.
            "X-Amz-Content-SHA256": hashlib.sha256(data).hexdigest(),
        },
    )
    SigV4Auth(credentials, "aoss", region).add_auth(request)

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")
    }
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _create_index(endpoint: str, index: str, region: str, dimension: int) -> None:
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("no AWS credentials available")

    url = _url(endpoint, index)
    body = _body(dimension)

    # AOSS data access policies propagate per-principal, so retry 403s.
    deadline = time.time() + 180
    while True:
        status, text = _send(credentials, region, "PUT", url, body)
        if status < 300 or "resource_already_exists_exception" in text:
            break
        if status != 403 or time.time() >= deadline:
            raise RuntimeError(f"PUT index failed: {status} {text}")
        time.sleep(10)

    deadline = time.time() + 120
    while time.time() < deadline:
        status, _ = _send(credentials, region, "GET", url, b"")
        if status < 300:
            print(f"index {index} ready")
            return
        time.sleep(5)
    raise RuntimeError(f"index {index} not visible after 120s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--index", default="bedrock-knowledge-base-default-index")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dimension", type=int, default=1024)
    args = parser.parse_args()

    try:
        _create_index(args.endpoint, args.index, args.region, args.dimension)
    except Exception as exc:  # surface a clean message and a non-zero exit
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
