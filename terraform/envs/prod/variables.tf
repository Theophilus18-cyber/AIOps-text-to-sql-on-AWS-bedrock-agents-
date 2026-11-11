variable "project" {
  description = "Project name used as the naming prefix"
  type        = string
  default     = "text2sql"
}

variable "env" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "model_id" {
  description = "Bedrock inference profile ID for the agent"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-6"
}

variable "model_foundation_id" {
  description = "Underlying foundation model the inference profile routes to (for IAM)"
  type        = string
  default     = "anthropic.claude-sonnet-4-6"
}

variable "embedding_model_id" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "bytes_scanned_limit" {
  description = "Athena per-query bytes-scanned cutoff (bytes)"
  type        = number
  default     = 536870912 # 512 MiB
}

variable "athena_results_prefix" {
  description = "Athena results prefix in the lake bucket"
  type        = string
  default     = "athena-results"
}

variable "docs_prefix" {
  description = "Approved schema docs prefix in the docs bucket"
  type        = string
  default     = "schema-docs/approved/"
}

variable "glossary_prefix" {
  description = "Glossary YAML prefix in the docs bucket"
  type        = string
  default     = "glossary/"
}

variable "max_rows" {
  description = "Maximum result rows returned by run_sql"
  type        = number
  default     = 100
}

variable "max_cell_chars" {
  description = "Maximum characters per result cell"
  type        = number
  default     = 500
}

variable "max_query_length" {
  description = "Maximum SQL length accepted by the validator"
  type        = number
  default     = 8192
}

variable "max_limit" {
  description = "Maximum allowed LIMIT in generated SQL"
  type        = number
  default     = 1000
}
