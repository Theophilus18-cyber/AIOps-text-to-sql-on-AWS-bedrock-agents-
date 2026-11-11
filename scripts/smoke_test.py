"""Ask the deployed orchestrator a question and print its answer.

Usage: ``python scripts/smoke_test.py --env dev [--question "..."]``
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3

from _tf import terraform_output

DEFAULT_QUESTION = "What was the total transaction amount?"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="dev", help="Terraform environment")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    name = terraform_output(args.env, "orchestrator_function_name")

    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"question": args.question}),
    )
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    if "FunctionError" in response:
        print(f"orchestrator error: {payload}", file=sys.stderr)
        return 1

    print(f"Q: {args.question}\n")
    print(payload.get("answer") or payload.get("error") or json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
