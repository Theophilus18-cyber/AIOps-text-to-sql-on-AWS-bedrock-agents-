data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "this" {
  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.docs_bucket_arn, "${var.docs_bucket_arn}/*"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
  statement {
    actions   = ["aoss:APIAccessAll"]
    resources = [var.collection_arn]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "kb-policy"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = "${var.role_name}-aoss"
  type = "data"
  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${var.collection_name}"]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems",
          ]
        },
        {
          ResourceType = "index"
          Resource     = ["index/${var.collection_name}/*"]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
          ]
        },
      ]
      Principal = [
        aws_iam_role.this.arn,
        data.aws_caller_identity.current.arn,
      ]
    }
  ])
}

# Bedrock KB expects the vector index to already exist, so create it once the
# data access policy is in place and the collection is active.
resource "null_resource" "index" {
  depends_on = [aws_opensearchserverless_access_policy.data]

  triggers = {
    endpoint = var.collection_endpoint
    region   = var.region
  }

  provisioner "local-exec" {
    working_dir = abspath("${path.module}/../../..")
    command     = "python scripts/create_aoss_index.py --endpoint ${var.collection_endpoint} --region ${var.region}"
  }
}

resource "aws_bedrockagent_knowledge_base" "this" {
  depends_on = [null_resource.index]

  name        = var.name
  description = var.description
  role_arn    = aws_iam_role.this.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = var.collection_arn
      vector_index_name = "bedrock-knowledge-base-default-index"
      field_mapping {
        metadata_field = "AMAZON_BEDROCK_METADATA"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        vector_field   = "bedrock-knowledge-base-default-vector"
      }
    }
  }
}

resource "aws_bedrockagent_data_source" "this" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.this.id
  name              = var.data_source_name
  description       = "Schema documentation markdown (one table per document)"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = var.docs_bucket_arn
      inclusion_prefixes = [var.inclusion_prefix]
    }
  }

  data_deletion_policy = "DELETE"

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "NONE"
    }
  }
}
