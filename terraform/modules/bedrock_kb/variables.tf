variable "name" {
  description = "Knowledge base name"
  type        = string
}

variable "description" {
  description = "Knowledge base description"
  type        = string
  default     = "Schema documentation knowledge base"
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "embedding_model_id" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "docs_bucket_arn" {
  description = "Schema docs bucket ARN"
  type        = string
}

variable "inclusion_prefix" {
  description = "S3 prefix to ingest (one table = one document)"
  type        = string
  default     = "schema-docs/approved/"
}

variable "data_source_name" {
  description = "Data source name"
  type        = string
}

variable "collection_arn" {
  description = "OpenSearch Serverless collection ARN"
  type        = string
}

variable "collection_name" {
  description = "OpenSearch Serverless collection name"
  type        = string
}

variable "collection_endpoint" {
  description = "OpenSearch Serverless collection endpoint"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN"
  type        = string
}

variable "role_name" {
  description = "KB service role name"
  type        = string
}
