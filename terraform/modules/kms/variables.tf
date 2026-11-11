variable "name_prefix" {
  description = "Prefix for the KMS alias (e.g. 'text2sql-dev')"
  type        = string
}

variable "name" {
  description = "Short name appended to the alias (e.g. 'app')"
  type        = string
}

variable "description" {
  description = "Description of the KMS key"
  type        = string
}

variable "deletion_window_in_days" {
  description = "Number of days before key deletion is permanent"
  type        = number
  default     = 7
}

variable "enable_key_rotation" {
  description = "Enable automatic annual key rotation"
  type        = bool
  default     = true
}

variable "policy" {
  description = "Optional full key policy JSON. Defaults to account-root admin (IAM delegation)."
  type        = string
  default     = null
}
