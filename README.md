# Ask Your Data Lake Anything

**Natural-language to SQL on AWS — turn "what was our fraud rate in Texas last
quarter?" into an audited, safe Athena query and a plain-English answer.**

> A production-grade text-to-SQL system. Business users ask questions in
> English; a Claude-powered orchestrator reads your schema, writes and checks
> the SQL, runs it on Athena, and explains the answer. Built for **any** dataset
> in your S3 data lake — not just one hardcoded table.

---

## The problem

Your data lives in S3, catalogued in Glue and queryable through Athena. That's
great for engineers — and a wall for everyone else. To answer a simple business
question, someone has to:

1. know which tables and columns exist,
2. write correct SQL (without touching PII),
3. run it, and
4. translate the result back into English.

That someone is usually your over-subscribed data team. This project removes
them from the hot path: it gives **everyone** a safe, self-serve window into the
lake, while keeping the guardrails an auditor would insist on.

## What it does

```
  "What was spend by category last month?"
                    │
                    ▼
        ┌───────────────────────────────┐
        │  Orchestrator (Claude Sonnet) │   Bedrock Runtime converse + tools
        │  Bedrock Guardrail attached   │   (no retired Agents Classic)
        └───────────────┬───────────────┘
                        │  loop: the model calls the two tools below
        ┌───────────────┴───────────────┐
        ▼                               ▼
  get_schema_context(q)            run_sql(sql)
  Bedrock KB Retrieve              sqlglot allow-list check
        │                               │
        ▼                               ▼
  OpenSearch Serverless            Athena → Glue catalog → S3 lake
  (vector embeddings)              (results capped, PII guarded)
```

The orchestrator is **code-defined**: a Lambda drives the Bedrock Runtime
[`converse`](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
tool-use loop. It exposes two tools to the model:

- **`get_schema_context(question)`** — retrieves the top-k relevant table
  documents from a Bedrock Knowledge Base (so the model never guesses table or
  column names).
- **`run_sql(sql)`** — validates the SQL against a **dynamic allow-list** built
  from the live Glue catalog, then executes it on Athena and returns capped
  results.

The model reads the schema, writes the query, fixes it if it's rejected, and
answers in plain English with the exact SQL it ran.

## Why it's safe

- **SQL is untrusted.** A `sqlglot` validator enforces one read-only
  `SELECT`/CTE, a table allow-list derived from Glue (refreshed every 5 min),
  a mandatory `LIMIT`, and a length cap — deny-by-default.
- **PII stays out of answers.** A Bedrock Guardrail masks card numbers, names
  and addresses; the system prompt forbids returning raw PII and prefers
  aggregates.
- **Least-privilege IAM.** The orchestrator can only read the lake, write Athena
  results to one prefix, and `Retrieve` from one KB — with `aws:SourceArn`
  trust conditions on every role.
- **Encryption everywhere.** SSE-KMS on S3, Athena results, Lambda environment
  variables, and the vector store.
- **Cost-capped.** An Athena workgroup enforces a per-query bytes-scanned limit.

## Dataset-agnostic by design

Nothing here knows about a "credit card" table. The crawler discovers whatever
is under `raw/`, the doc-builder documents every table it finds, and the SQL
allow-list comes from the live Glue catalog. Add a dataset by dropping data
into `s3://<lake>/raw/<table>/` and re-running the refresh — no code changes.

## Tech stack

| Layer | Choice |
|---|---|
| Query engine | Amazon Athena (Glue Data Catalog + S3 lake) |
| Orchestration | AWS Lambda + Bedrock Runtime `converse` (code-defined tool loop) |
| Model | Claude Sonnet (`us.anthropic.claude-sonnet-4-6`) |
| Embeddings | Amazon Titan Text Embeddings v2 |
| Vector store | Amazon OpenSearch Serverless (via Bedrock Knowledge Bases) |
| Guardrails | Amazon Bedrock Guardrails (PII masking + prompt-attack filtering) |
| Validation | `sqlglot` (Athena/Trino dialect) |
| IaC | Terraform (remote S3 state + DynamoDB locking) |

## Repository layout

```
.
├── Makefile                         # build / deploy / test entry points
├── pyproject.toml                   # ruff, mypy, pytest config
├── PLAN.md                          # design, costs, risks, phase plan
├── glossary/                        # human-authored table semantics + Q&A
├── src/
│   ├── common/                      # stdlib-only config/aws/logging helpers
│   ├── orchestrator/                # the converse tool-use loop (Lambda)
│   ├── action_group/                # get_schema_context + run_sql tools
│   │   ├── tools.py                 #   the two tool functions
│   │   ├── sql_validator.py         #   sqlglot allow-list / LIMIT validation
│   │   ├── athena_runner.py         #   Athena execution + result caps
│   │   └── kb_client.py             #   Bedrock KB Retrieve
│   ├── doc_builder/                 # refresh Lambda: Glue → Markdown → S3 + ingest
│   └── evaluation/                  # golden-set evaluation harness
├── scripts/                         # local (identity-run) operational scripts
│   ├── bootstrap_state.py           # create S3 tfstate bucket + DynamoDB lock
│   ├── build_lambdas.py             # zip the Lambda packages (manylinux wheels)
│   ├── create_aoss_index.py         # create the KB vector index in the collection
│   ├── prepare_and_upload_data.py   # CSV → partitioned Parquet → S3 raw/<table>/
│   ├── upload_glossary.py           # upload glossary/*.yaml → docs bucket
│   ├── refresh.py                   # crawler → doc-builder → KB ingestion
│   ├── smoke_test.py                # one question through the orchestrator
│   └── run_evaluation.py            # golden-set pass/fail report
├── terraform/
│   ├── modules/                     # kms, storage, glue_catalog, athena, vector_store,
│   │                                # bedrock_kb, bedrock_guardrail, lambda_function
│   └── envs/{dev,prod}/             # root modules wiring everything + IAM
└── tests/unit/                      # SQL-validator, renderer, publisher, tools tests
```

## Quick start

**Prerequisites:** Terraform ≥ 1.10, AWS CLI (authenticated via an **IAM
identity**, not SSO), Python 3.12, GNU `make`.

1. **Bootstrap remote state** (once per environment):

   ```bash
   python scripts/bootstrap_state.py --env dev
   ```

2. **Build the Lambda packages:**

   ```bash
   make build          # → dist/orchestrator.zip, dist/doc_builder.zip
   ```

3. **Deploy:**

   ```bash
   make init           # remote S3 backend + DynamoDB locking (no hardcoded IDs)
   make plan           # ALWAYS review the plan first
   make apply          # only after you approve the plan
   ```

4. **Load a dataset:**

   ```bash
   python scripts/prepare_and_upload_data.py --csv path/to/credit_card.csv --env dev
   ```

5. **Document the schema and ingest it** (add `glossary/<table>.yaml` first):

   ```bash
   make refresh        # crawler → doc-builder → KB ingestion
   ```

6. **Ask a question:**

   ```bash
   make smoke          # one sample question through the orchestrator
   make evaluate       # golden-set pass/fail report
   ```

## Quality gates

```bash
make test             # pytest (adversarial SQL-validator suite)
make fmt              # terraform fmt + ruff format
make lint             # ruff check
make typecheck        # mypy
make scan             # checkov (if installed)
```

## Security notes

- No account IDs, regions, or ARNs are hardcoded — they're read from
  `aws sts get-caller-identity` and Terraform outputs at runtime.
- No long-lived access keys are created; the CLI uses your current IAM identity.
- Data and retrieved documents are treated as **untrusted**; the model is told
  to ignore instructions found inside them.

See [PLAN.md](PLAN.md) for the full design, cost model and risk register.
