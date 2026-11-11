data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["athena.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.workgroup_name}-execution"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# Athena execution role: read-only on the lake, writes only the results prefix,
# catalog read, and CMK access.
data "aws_iam_policy_document" "execution" {
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.lake_bucket_arn, "${var.lake_bucket_arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.results_bucket}/${var.results_prefix}/*"]
  }
  statement {
    actions   = ["s3:GetBucketLocation", "s3:GetObject"]
    resources = ["arn:aws:s3:::${var.results_bucket}", "arn:aws:s3:::${var.results_bucket}/${var.results_prefix}/*"]
  }
  statement {
    actions = [
      "glue:GetTable", "glue:GetTables", "glue:GetDatabase",
      "glue:GetPartition", "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:catalog",
      "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:database/${var.database_name}",
      "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.database_name}/*",
    ]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "execution-policy"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

resource "aws_athena_workgroup" "this" {
  name          = var.workgroup_name
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_limit
    execution_role                     = aws_iam_role.execution.arn

    result_configuration {
      output_location = "s3://${var.results_bucket}/${var.results_prefix}/"
      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = var.kms_key_arn
      }
    }
  }
}
