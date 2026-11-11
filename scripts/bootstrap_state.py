"""Create the Terraform remote state bucket and DynamoDB lock table (idempotent).

Run once per environment before the first ``terraform init``::

    python scripts/bootstrap_state.py --env dev --region us-east-1

Uses the current AWS identity (an SSO profile exported via environment variables,
or the default profile). Never creates long-lived access keys.
"""

from __future__ import annotations

import argparse
import logging
import sys

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("bootstrap_state")


def _account_id(sts: boto3.client) -> str:
    return str(sts.get_caller_identity()["Account"])


def _ensure_bucket(s3: boto3.client, name: str, region: str) -> None:
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=name)
        else:
            s3.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": region})
        logger.info("created bucket %s", name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise
        logger.info("bucket %s already exists", name)

    s3.put_bucket_versioning(Bucket=name, VersioningConfiguration={"Status": "Enabled"})
    s3.put_public_access_block(
        Bucket=name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    # SSE-S3 is used here because no CMK exists yet at bootstrap time; the lake/docs/artifacts
    # buckets created later by Terraform use the customer-managed KMS key.
    s3.put_bucket_encryption(
        Bucket=name,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    logger.info("bucket %s hardened (versioning, block-public, SSE-S3)", name)


def _ensure_lock_table(dynamodb: boto3.client, name: str) -> None:
    try:
        dynamodb.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("created lock table %s", name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceInUseException":
            raise
        logger.info("lock table %s already exists", name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="text2sql")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    sts = boto3.client("sts", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)
    dynamodb = boto3.client("dynamodb", region_name=args.region)

    account = _account_id(sts)
    bucket = f"{args.project}-{args.env}-tfstate-{account}"
    table = f"{args.project}-{args.env}-tfstate-lock"

    logger.info("account %s region %s", account, args.region)
    _ensure_bucket(s3, bucket, args.region)
    _ensure_lock_table(dynamodb, table)

    logger.info("done: bucket=%s table=%s", bucket, table)
    print(bucket)
    return 0


if __name__ == "__main__":
    sys.exit(main())
