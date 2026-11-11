"""Upload local glossary YAML files to the docs bucket.

Each ``glossary/*.yaml`` file maps table name -> glossary entry.  The
doc-builder loads every file under the glossary prefix and merges them, so
adding a file here is how a new dataset gets its business semantics without
code changes.

Usage: ``python scripts/upload_glossary.py --env dev``
"""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3

from _tf import terraform_output

PREFIX = "glossary"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="dev", help="Terraform environment")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bucket = terraform_output(args.env, "docs_bucket")
    glossary_dir = Path(__file__).resolve().parent.parent / "glossary"
    s3 = boto3.client("s3")

    uploaded = 0
    for path in sorted(glossary_dir.glob("*.yaml")):
        key = f"{PREFIX}/{path.name}"
        s3.put_object(Bucket=bucket, Key=key, Body=path.read_bytes())
        print(f"uploaded s3://{bucket}/{key}")
        uploaded += 1

    print(f"uploaded {uploaded} glossary file(s).")
    return 0 if uploaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
