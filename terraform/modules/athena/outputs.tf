output "workgroup_name" {
  description = "Athena workgroup name"
  value       = aws_athena_workgroup.this.name
}

output "execution_role_arn" {
  description = "Athena execution role ARN"
  value       = aws_iam_role.execution.arn
}
