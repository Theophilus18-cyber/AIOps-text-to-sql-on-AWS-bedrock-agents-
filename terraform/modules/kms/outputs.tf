output "key_id" {
  description = "KMS key ID"
  value       = aws_kms_key.this.key_id
}

output "arn" {
  description = "KMS key ARN"
  value       = aws_kms_key.this.arn
}

output "alias_name" {
  description = "KMS key alias (e.g. alias/text2sql-dev-app)"
  value       = aws_kms_alias.this.name
}
