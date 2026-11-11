resource "aws_lambda_function" "this" {
  function_name                  = var.function_name
  role                           = var.role_arn
  handler                        = var.handler
  runtime                        = var.runtime
  filename                       = var.zip_path
  source_code_hash               = filebase64sha256(var.zip_path)
  timeout                        = var.timeout
  memory_size                    = var.memory_size
  kms_key_arn                    = var.kms_key_arn
  reserved_concurrent_executions = var.reserved_concurrent_executions

  environment {
    variables = var.environment
  }

  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }
}
