output "guardrail_id" {
  description = "Guardrail ID"
  value       = aws_bedrock_guardrail.this.guardrail_id
}

output "guardrail_arn" {
  description = "Guardrail ARN"
  value       = aws_bedrock_guardrail.this.guardrail_arn
}

output "version" {
  description = "Published guardrail version"
  value       = aws_bedrock_guardrail_version.this.version
}
