# Bootstrap

The Terraform remote state bucket and DynamoDB lock table are created once per
environment by a script, not by Terraform (they must exist before the first
`terraform init`):

```bash
python scripts/bootstrap_state.py --env dev --region us-east-1
```

This creates:

- S3 bucket `text2sql-<env>-tfstate-<account_id>` (versioning, block-public,
  SSE-S3 — no CMK exists yet at this point).
- DynamoDB lock table `text2sql-<env>-tfstate-lock` (pay-per-request).

After that, `make init` points the `backend "s3"` at these resources.
