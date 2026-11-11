variable "database_name" {
  description = "Glue catalog database name"
  type        = string
}

variable "crawler_name" {
  description = "Glue crawler name (unique per account+region)"
  type        = string
}

variable "s3_path" {
  description = "S3 path to crawl (s3://<lake>/raw/)"
  type        = string
}

variable "lake_bucket_arn" {
  description = "Data lake bucket ARN"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for decrypting lake objects"
  type        = string
}
