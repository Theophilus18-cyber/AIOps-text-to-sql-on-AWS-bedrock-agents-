output "account_id" {
  description = "AWS account ID"
  value       = local.account_id
}

output "region" {
  description = "AWS region"
  value       = local.region
}

output "lake_bucket" {
  description = "Data lake bucket name"
  value       = module.lake_bucket.bucket
}

output "docs_bucket" {
  description = "Schema docs bucket name"
  value       = module.docs_bucket.bucket
}

output "glue_database" {
  description = "Glue catalog database name"
  value       = module.glue_catalog.database_name
}

output "athena_workgroup" {
  description = "Athena workgroup name"
  value       = module.athena.workgroup_name
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = module.bedrock_kb.knowledge_base_id
}

output "collection_arn" {
  description = "OpenSearch Serverless collection ARN"
  value       = module.vector_store.collection_arn
}

output "orchestrator_function_name" {
  description = "Orchestrator Lambda function name"
  value       = module.orchestrator.function_name
}

output "glue_crawler" {
  description = "Glue crawler name"
  value       = module.glue_catalog.crawler_name
}

output "doc_builder_function_name" {
  description = "Doc-builder Lambda function name"
  value       = module.doc_builder.function_name
}
