variable "name" {
  description = "Globally unique bucket name"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for SSE-KMS. Omit to use SSE-S3 (AES256)."
  type        = string
  default     = null
}

variable "versioning" {
  description = "Enable object versioning"
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Delete the bucket even if it contains objects"
  type        = bool
  default     = false
}

variable "enable_lifecycle" {
  description = "Enable the baseline lifecycle rule (abort incomplete multipart uploads)"
  type        = bool
  default     = true
}
