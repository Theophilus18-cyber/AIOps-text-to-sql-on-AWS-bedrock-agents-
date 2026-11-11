"""Refresh the schema documentation end-to-end.

Runs the Glue crawler to (re)discover tables, waits for it to finish, then
invokes the doc-builder Lambda, which reads Glue metadata, renders Markdown
docs, publishes them to the docs bucket, and starts a Bedrock KB ingestion job.

Usage: ``python scripts/refresh.py --env dev``
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import boto3

from _tf import terraform_output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="dev", help="Terraform environment")
    parser.add_argument("--skip-crawler", action="store_true", help="Invoke doc-builder only")
    return parser.parse_args()


def _run_crawler(glue: Any, name: str) -> None:
    glue.start_crawler(Name=name)
    print(f"crawler '{name}' started; waiting for it to finish ...")
    while True:
        state = glue.get_crawler(Name=name)["Crawler"]["State"]
        if state == "READY":
            print("crawler finished.")
            return
        if state in ("FAILED", "STOPPING", "STOPPED"):
            raise RuntimeError(f"crawler ended in state {state}")
        time.sleep(10)


def _invoke_builder(lam: Any, name: str) -> dict[str, Any]:
    response = lam.invoke(
        FunctionName=name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"mode": "build"}),
    )
    payload: dict[str, Any] = json.loads(response["Payload"].read().decode("utf-8"))
    if "FunctionError" in response:
        raise RuntimeError(f"doc-builder failed: {payload}")
    return payload


def main() -> int:
    args = _parse_args()

    if not args.skip_crawler:
        crawler = terraform_output(args.env, "glue_crawler")
        _run_crawler(boto3.client("glue"), crawler)

    builder = terraform_output(args.env, "doc_builder_function_name")
    summary = _invoke_builder(boto3.client("lambda"), builder)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
