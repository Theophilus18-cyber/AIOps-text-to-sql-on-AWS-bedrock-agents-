resource "aws_bedrock_guardrail" "this" {
  name                      = var.name
  description               = var.description
  blocked_input_messaging   = var.blocked_input_messaging
  blocked_outputs_messaging = var.blocked_outputs_messaging

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    # The four semantic filters are kept at HIGH on input to reject malicious or
    # inappropriate user prompts, but NONE on output. This orchestrator is a
    # read-only text-to-SQL analyst over a bank's own transaction data, and its
    # answers are aggregates, capped tables and charts. Output-side semantic
    # filtering here only produced false positives that blocked legitimate
    # analytical answers (e.g. a June transactions summary), so output blocking
    # is left to the sensitive-information policy (PII masking) below.
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "NAME"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "ADDRESS"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "DRIVER_ID"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "IP_ADDRESS"
      action = "ANONYMIZE"
    }
  }

  # No word_policy_config (managed PROFANITY list): the managed list matches on
  # both input and output and false-positives on transaction/merchant data, which
  # is what intermittently blocked legitimate analytical answers. Profanity in a
  # user prompt is already declined by the system prompt, and PII masking above
  # still covers the real data-sensitivity concern.
}

resource "aws_bedrock_guardrail_version" "this" {
  guardrail_arn = aws_bedrock_guardrail.this.guardrail_arn
  # Bedrock guardrail versions are immutable snapshots. This resource depends only
  # on the ARN, so editing the guardrail above does NOT recreate it — the
  # orchestrator would stay pinned to a stale snapshot. Bump this description
  # (a force-new attribute) whenever the guardrail content changes.
  description = "v3"
}
