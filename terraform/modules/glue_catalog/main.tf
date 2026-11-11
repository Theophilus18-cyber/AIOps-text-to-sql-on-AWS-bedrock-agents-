data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_glue_catalog_database" "this" {
  name = var.database_name
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "crawler" {
  name               = var.crawler_name
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# Least-privilege crawler policy: read the lake, manage the catalog database,
# decrypt with the CMK, and write CloudWatch logs.
data "aws_iam_policy_document" "crawler" {
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.lake_bucket_arn, "${var.lake_bucket_arn}/*"]
  }
  statement {
    actions = [
      "glue:GetDatabase", "glue:GetDatabases", "glue:UpdateDatabase",
      "glue:GetTable", "glue:GetTables", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable",
      "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition",
      "glue:CreatePartition", "glue:BatchCreatePartition", "glue:UpdatePartition",
      "glue:DeletePartition", "glue:BatchDeletePartition",
      "glue:CreatePartitionIndex", "glue:DeletePartitionIndex",
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
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"]
  }
}

resource "aws_iam_role_policy" "crawler" {
  name   = "crawler-policy"
  role   = aws_iam_role.crawler.id
  policy = data.aws_iam_policy_document.crawler.json
}

resource "aws_glue_crawler" "this" {
  name          = var.crawler_name
  database_name = aws_glue_catalog_database.this.name
  role          = aws_iam_role.crawler.arn

  s3_target {
    path = var.s3_path
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  # Preserve Hive-style partitions (year=…/month=…) across recrawls.
  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })
}
