provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  prefix     = "${var.project}-${var.env}"
  glue_db    = "${replace(var.project, "-", "_")}_${var.env}_lake"
  zip_root   = abspath("${path.module}/../../..")
}

# ---------------------------------------------------------------------------
# KMS + storage (Phase 1)
# ---------------------------------------------------------------------------
module "kms" {
  source      = "../../modules/kms"
  name_prefix = local.prefix
  name        = "app"
  description = "Application KMS key for ${local.prefix}"
}

module "lake_bucket" {
  source      = "../../modules/storage"
  name        = "${local.prefix}-lake-${local.account_id}"
  kms_key_arn = module.kms.arn
}

module "docs_bucket" {
  source      = "../../modules/storage"
  name        = "${local.prefix}-docs-${local.account_id}"
  kms_key_arn = module.kms.arn
}

module "artifacts_bucket" {
  source      = "../../modules/storage"
  name        = "${local.prefix}-artifacts-${local.account_id}"
  kms_key_arn = module.kms.arn
}

# ---------------------------------------------------------------------------
# Glue catalog + Athena (Phase 2)
# ---------------------------------------------------------------------------
module "glue_catalog" {
  source          = "../../modules/glue_catalog"
  database_name   = local.glue_db
  crawler_name    = "${local.prefix}-lake-crawler"
  s3_path         = "s3://${module.lake_bucket.bucket}/raw/"
  lake_bucket_arn = module.lake_bucket.arn
  kms_key_arn     = module.kms.arn
}

module "athena" {
  source              = "../../modules/athena"
  workgroup_name      = local.prefix
  results_bucket      = module.lake_bucket.bucket
  results_prefix      = var.athena_results_prefix
  kms_key_arn         = module.kms.arn
  lake_bucket_arn     = module.lake_bucket.arn
  database_name       = module.glue_catalog.database_name
  bytes_scanned_limit = var.bytes_scanned_limit
}

# ---------------------------------------------------------------------------
# Vector store: OpenSearch Serverless (Phase 3)
# ---------------------------------------------------------------------------
module "vector_store" {
  source          = "../../modules/vector_store"
  name_prefix     = local.prefix
  collection_name = "${local.prefix}-kb"
}

# ---------------------------------------------------------------------------
# Bedrock Knowledge Base (Phase 3)
# ---------------------------------------------------------------------------
module "bedrock_kb" {
  source              = "../../modules/bedrock_kb"
  name                = "${local.prefix}-kb"
  region              = local.region
  embedding_model_id  = var.embedding_model_id
  docs_bucket_arn     = module.docs_bucket.arn
  data_source_name    = "${local.prefix}-schema-docs"
  collection_arn      = module.vector_store.collection_arn
  collection_name     = module.vector_store.collection_name
  collection_endpoint = module.vector_store.collection_endpoint
  kms_key_arn         = module.kms.arn
  role_name           = "${local.prefix}-kb"
}

# ---------------------------------------------------------------------------
# Bedrock Guardrail (Phase 4)
# ---------------------------------------------------------------------------
module "bedrock_guardrail" {
  source = "../../modules/bedrock_guardrail"
  name   = "${local.prefix}-guardrail"
}

# ---------------------------------------------------------------------------
# Orchestrator Lambda (Phase 4)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "orchestrator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "orchestrator" {
  name               = "${local.prefix}-orchestrator"
  assume_role_policy = data.aws_iam_policy_document.orchestrator_assume.json
}

data "aws_iam_policy_document" "orchestrator" {
  statement {
    actions = [
      "glue:GetDatabase", "glue:GetTables", "glue:GetTable", "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:glue:${local.region}:${local.account_id}:catalog",
      "arn:aws:glue:${local.region}:${local.account_id}:database/${module.glue_catalog.database_name}",
      "arn:aws:glue:${local.region}:${local.account_id}:table/${module.glue_catalog.database_name}/*",
    ]
  }
  statement {
    actions = [
      "athena:StartQueryExecution", "athena:GetQueryExecution",
      "athena:GetQueryResults", "athena:StopQueryExecution",
    ]
    resources = ["arn:aws:athena:${local.region}:${local.account_id}:workgroup/${module.athena.workgroup_name}"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [module.lake_bucket.arn, "${module.lake_bucket.arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${module.lake_bucket.arn}/${var.athena_results_prefix}/*"]
  }
  statement {
    actions   = ["bedrock:Retrieve"]
    resources = [module.bedrock_kb.knowledge_base_arn]
  }
  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${local.region}::foundation-model/${var.model_id}"]
  }
  statement {
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [module.bedrock_guardrail.guardrail_arn]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [module.kms.arn]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:*"]
  }
}

resource "aws_iam_role_policy" "orchestrator" {
  name   = "policy"
  role   = aws_iam_role.orchestrator.id
  policy = data.aws_iam_policy_document.orchestrator.json
}

module "orchestrator" {
  source                         = "../../modules/lambda_function"
  function_name                  = "${local.prefix}-orchestrator"
  role_arn                       = aws_iam_role.orchestrator.arn
  handler                        = "handler.lambda_handler"
  zip_path                       = "${local.zip_root}/dist/orchestrator.zip"
  timeout                        = 120
  memory_size                    = 256
  kms_key_arn                    = module.kms.arn
  environment = {
    REGION                = local.region
    ATHENA_DATABASE       = module.glue_catalog.database_name
    ATHENA_WORKGROUP      = module.athena.workgroup_name
    ATHENA_RESULTS_BUCKET = module.lake_bucket.bucket
    ATHENA_RESULTS_PREFIX = var.athena_results_prefix
    KB_ID                 = module.bedrock_kb.knowledge_base_id
    MODEL_ID              = var.model_id
    GUARDRAIL_ID          = module.bedrock_guardrail.guardrail_arn
    GUARDRAIL_VERSION     = module.bedrock_guardrail.version
    MAX_ROWS              = tostring(var.max_rows)
    MAX_CELL_CHARS        = tostring(var.max_cell_chars)
    MAX_QUERY_LENGTH      = tostring(var.max_query_length)
    MAX_LIMIT             = tostring(var.max_limit)
  }
}

# ---------------------------------------------------------------------------
# Doc-builder Lambda (Phase 3)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "doc_builder_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "doc_builder" {
  name               = "${local.prefix}-doc-builder"
  assume_role_policy = data.aws_iam_policy_document.doc_builder_assume.json
}

data "aws_iam_policy_document" "doc_builder" {
  statement {
    actions = [
      "glue:GetDatabase", "glue:GetTables", "glue:GetTable", "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:glue:${local.region}:${local.account_id}:catalog",
      "arn:aws:glue:${local.region}:${local.account_id}:database/${module.glue_catalog.database_name}",
      "arn:aws:glue:${local.region}:${local.account_id}:table/${module.glue_catalog.database_name}/*",
    ]
  }
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [module.docs_bucket.arn, "${module.docs_bucket.arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${module.docs_bucket.arn}/${var.docs_prefix}*"]
  }
  statement {
    actions = ["bedrock:StartIngestionJob"]
    resources = [
      "arn:aws:bedrock:${local.region}:${local.account_id}:knowledge-base/${module.bedrock_kb.knowledge_base_id}/data-source/${module.bedrock_kb.data_source_id}",
    ]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [module.kms.arn]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:*"]
  }
}

resource "aws_iam_role_policy" "doc_builder" {
  name   = "policy"
  role   = aws_iam_role.doc_builder.id
  policy = data.aws_iam_policy_document.doc_builder.json
}

module "doc_builder" {
  source        = "../../modules/lambda_function"
  function_name = "${local.prefix}-doc-builder"
  role_arn      = aws_iam_role.doc_builder.arn
  handler       = "handler.lambda_handler"
  zip_path      = "${local.zip_root}/dist/doc_builder.zip"
  timeout       = 300
  memory_size   = 512
  kms_key_arn   = module.kms.arn
  environment = {
    REGION          = local.region
    GLUE_DATABASE   = module.glue_catalog.database_name
    DOCS_BUCKET     = module.docs_bucket.bucket
    GLOSSARY_PREFIX = var.glossary_prefix
    DOCS_PREFIX     = var.docs_prefix
    KB_ID           = module.bedrock_kb.knowledge_base_id
    DATA_SOURCE_ID  = module.bedrock_kb.data_source_id
  }
}
