output "bucket" {
  description = "Bucket name"
  value       = aws_s3_bucket.this.bucket
}

output "id" {
  description = "Bucket ID (name)"
  value       = aws_s3_bucket.this.id
}

output "arn" {
  description = "Bucket ARN"
  value       = aws_s3_bucket.this.arn
}
