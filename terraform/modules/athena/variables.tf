variable "workgroup_name" {
  description = "Athena workgroup name"
  type        = string
}

variable "results_bucket" {
  description = "S3 bucket for Athena query results"
  type        = string
}

variable "results_prefix" {
  description = "Prefix inside the results bucket"
  type        = string
  default     = "athena-results"
}

variable "kms_key_arn" {
  description = "KMS key ARN for encrypting results"
  type        = string
}

variable "lake_bucket_arn" {
  description = "Data lake bucket ARN (read-only for Athena)"
  type        = string
}

variable "database_name" {
  description = "Glue catalog database Athena queries read from"
  type        = string
}

variable "bytes_scanned_limit" {
  description = "Per-query bytes-scanned cutoff (bytes). Default 1 GiB."
  type        = number
  default     = 1073741824
}
