output "knowledge_base_id" {
  description = "Knowledge base ID"
  value       = aws_bedrockagent_knowledge_base.this.id
}

output "knowledge_base_arn" {
  description = "Knowledge base ARN"
  value       = aws_bedrockagent_knowledge_base.this.arn
}

output "data_source_id" {
  description = "Data source ID"
  value       = aws_bedrockagent_data_source.this.id
}

output "role_arn" {
  description = "KB service role ARN"
  value       = aws_iam_role.this.arn
}
