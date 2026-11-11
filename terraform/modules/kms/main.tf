data "aws_caller_identity" "current" {}

# Default key policy: grant the account root (which delegates access to IAM
# identities in this account). Service-specific grants are added per-consumer
# in later phases via the `policy` variable.
data "aws_iam_policy_document" "key" {
  statement {
    sid       = "EnableRootAccess"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "this" {
  description             = var.description
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = var.enable_key_rotation
  policy                  = var.policy != null ? var.policy : data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name_prefix}-${var.name}"
  target_key_id = aws_kms_key.this.key_id
}
