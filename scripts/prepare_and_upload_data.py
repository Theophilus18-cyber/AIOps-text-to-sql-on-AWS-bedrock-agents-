"""Prepare the raw CSV and upload it to the data lake.

Transforms the Kaggle credit-card dataset into partitioned Parquet under
``s3://<lake>/raw/credit_card_transactions/`` so the Glue crawler discovers
Hive-style partitions (``year=YYYY/month=MM``):

* drop the ``Unnamed: 0`` index column,
* rename ``long`` -> ``longitude`` (reserved-ish name),
* derive integer ``year`` / ``month`` partition columns from
  ``trans_date_trans_time``,
* coerce ``is_fraud`` to int and ``amt`` to float.

Run from the repo root: ``python scripts/prepare_and_upload_data.py --csv <file>``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import boto3
import pandas as pd

from _tf import terraform_output

RAW_PREFIX = "raw"
_MONTHS = {m: f"{m:02d}" for m in range(1, 13)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to the source CSV")
    parser.add_argument("--env", default="dev", help="Terraform environment")
    parser.add_argument(
        "--table", default="credit_card_transactions", help="Table name (S3 subfolder under raw/)"
    )
    parser.add_argument("--no-upload", action="store_true", help="Write Parquet only")
    return parser.parse_args()


def transform(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    df = df.rename(columns={"long": "longitude"})

    ts = pd.to_datetime(df["trans_date_trans_time"], errors="coerce")
    df["year"] = ts.dt.year.astype("Int64")
    df["month"] = ts.dt.month.astype("Int64")

    if df["year"].isna().any() or df["month"].isna().any():
        raise RuntimeError("Some trans_date_trans_time values could not be parsed.")

    df["is_fraud"] = df["is_fraud"].astype(int)
    df["amt"] = df["amt"].astype(float)
    return df


def _upload_dir(local_dir: Path, bucket: str, table: str, s3: boto3.client) -> None:
    for path in sorted(local_dir.rglob("*.parquet")):
        key = f"{RAW_PREFIX}/{table}/{path.relative_to(local_dir).as_posix()}"
        s3.upload_file(str(path), bucket, key)
        print(f"uploaded s3://{bucket}/{key}")


def main() -> int:
    args = _parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"csv not found: {csv_path}", file=sys.stderr)
        return 2

    df = transform(csv_path)
    print(f"transformed {len(df):,} rows")

    tmp = Path(tempfile.mkdtemp(prefix="text2sql-"))
    try:
        df.to_parquet(tmp, partition_cols=["year", "month"], index=False)
        print(f"wrote partitioned parquet to {tmp}")

        if args.no_upload:
            print("skipping upload (--no-upload); files kept at", tmp)
            return 0

        bucket = terraform_output(args.env, "lake_bucket")
        s3 = boto3.client("s3")
        _upload_dir(tmp, bucket, args.table, s3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
