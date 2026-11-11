variable "function_name" {
  description = "Lambda function name"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN the function assumes"
  type        = string
}

variable "handler" {
  description = "Handler entrypoint, e.g. handler.lambda_handler"
  type        = string
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "zip_path" {
  description = "Absolute path to the deployment zip"
  type        = string
}

variable "timeout" {
  description = "Function timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Function memory in MB"
  type        = number
  default     = 256
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrency (null = unset)"
  type        = number
  default     = null
}

variable "kms_key_arn" {
  description = "KMS key ARN for environment variable encryption"
  type        = string
}

variable "environment" {
  description = "Environment variables"
  type        = map(string)
  default     = {}
}

variable "vpc_config" {
  description = "Optional VPC attachment"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}
