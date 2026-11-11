# PLAN — Production text-to-SQL on AWS (Bedrock + Athena + S3)

> **Note:** this is the original Phase-0 design document. The final architecture
> differs in two places: the vector store is **OpenSearch Serverless** (not Aurora
> pgvector), and the agent layer is a **code-defined orchestrator** using Bedrock
> Runtime `converse` (not the retired Bedrock Agents Classic). See [README.md](README.md)
> for the current design.

Status: **Historical — superseded by README.md for the current architecture.**

---

## 1. What I found (inspection results)

### 1.1 Data lake source
One file: `credit_card_transactions.csv` (354,147,665 bytes ≈ 354 MB).

| Attribute | Value |
|---|---|
| Rows | 1,296,675 |
| Columns | 24 |
| Delimiter | comma, header present, `\n` line endings |
| Date range | 2019-01-01 → 2020-06-21 (18 months) |
| Missing values | none, except `merch_zipcode` (195,973 empty) |

Columns (in file order):

`Unnamed: 0` (row index), `trans_date_trans_time`, `cc_num`, `merchant`, `category`, `amt`, `first`, `last`, `gender`, `street`, `city`, `state`, `zip`, `lat`, `long`, `city_pop`, `job`, `dob`, `trans_num`, `unix_time`, `merch_lat`, `merch_long`, `is_fraud`, `merch_zipcode`.

Distribution highlights:
- `is_fraud` (target): 1,289,169 non-fraud vs **7,506 fraud (0.58%)** — heavily imbalanced.
- `category`: 14 distinct values (`gas_transport`, `grocery_pos`, `home`, `shopping_pos`, `kids_pets`, `shopping_net`, `entertainment`, `food_dining`, `personal_care`, `health_fitness`, `misc_pos`, `misc_net`, `grocery_net`, `travel`).
- `gender`: F / M. `state`: 51 distinct.
- `amt`: mean $70.35, median $47.52, min $1.00, max $28,948.90.
- Types inferred: `amt` float64, `city_pop` int64, `is_fraud` int64, `unix_time` int; everything else string.

**PII-shaped columns (synthetic Kaggle data, but must be treated as sensitive):** `cc_num`, `first`, `last`, `street`, `city`, `zip`, `dob`, `trans_num`, `lat`/`long`, `merch_lat`/`merch_long`. This drives the Guardrail PII-masking requirement and the doc-builder/glossary documentation.

**Proposed data-prep transformations** (documented; veto if you disagree):
1. Drop `Unnamed: 0` — it is a redundant row index.
2. Rename `long` → `longitude` — `long` is a type keyword and a SQL footgun; `"long"` would otherwise need quoting everywhere.
3. Cast types properly (timestamp, int, double, string).
4. Partition by **`year` / `month`** derived from `trans_date_trans_time` → 18 partitions, one Parquet per partition under `s3://<lake>/raw/credit_card_transactions/`. One folder per table ⇒ one Glue table per folder.

Adding a second dataset = drop a new CSV into a new `raw/<table>/` folder + add `glossary/<table>.yaml` + re-run crawler. No code change.

### 1.2 AWS account / credentials
- Account: resolved at runtime via `aws sts get-caller-identity` (no account ID is hardcoded anywhere). Region default `us-east-1`.
- **Identity: an IAM *user* for bootstrapping. This project never creates or stores long-lived access keys.**
- AWS CLI 2.x, Terraform 1.11+ (≥ 1.10 ⇒ `use_lockfile` available), Python 3.12, boto3, pandas, pyarrow. `sqlglot` is vendored per-Lambda and listed in dev requirements for local tests.

---

## 2. Final design

### 2.1 Runtime (question → answer)
```
user question
   → Bedrock Agent (Claude)  [Guardrail attached, published version]
        → action group Lambda
             action get_schema_context(question) → Bedrock KB → top-k table markdown docs
             action run_sql(sql) → validate (sqlglot, Athena dialect) → Athena → capped rows
   → answer (text + the SQL used)
```
Athena reads the Glue catalog and S3. No LangChain. The agent writes SQL between the two action calls.

### 2.2 Refresh (on demand, `make refresh`)
```
scripts/refresh.py
  1. start Glue crawler, poll until done
  2. invoke doc-builder Lambda (async, then poll)
  3. poll KB ingestion job until complete
  4. print summary (tables added / changed / removed)
```
Doc-builder Lambda: read Glue catalog → merge `glossary/*.yaml` from S3 → render one markdown doc per table → hash each → upload only changed docs to `schema-docs/approved/` → delete docs for dropped tables → `StartIngestionJob` **only if something changed**, and handle "one ingestion job at a time" (catch the resource-in-use error and report it). New rows never trigger refresh; only schema/glossary changes do.

### 2.3 Vector store — **needs your decision** (Question 5)
Bedrock Knowledge Bases supported stores and trade-offs (current as of writing; re-verified in Phase 3):

| Store | Dev idle cost | Setup | Notes |
|---|---|---|---|
| **Amazon OpenSearch Serverless** | **~$345/mo** (min 2 OCUs always-on) | no VPC needed; can be public+policy-limited | best for prod/hybrid search; the spec's default |
| **Amazon Aurora Serverless v2 + pgvector** | **≈ $0 idle** (0 ACU min, scales to zero) | requires VPC; KB data source + doc-builder Lambda run in VPC | cheapest for dev; more netw
orking |
| **Pinecone / Redis / MongoDB (partner)** | subscription/usage fee, external | external account + API key, egress | third-party dependency |

My recommendation: **Aurora Serverless v2 (pgvector) for `dev`** to keep idle cost near zero, and keep OpenSearch Serverless as the `prod` choice — or, if you want dev == prod topology, OpenSearch Serverless everywhere and accept ~$345/mo. This one decision changes the Terraform (`vector_store` module) and the Lambda VPC story, so I need it before Phase 3.

### 2.4 Terraform vs Python split (matches spec)
- **Terraform**: KMS, S3 (lake + docs + artifacts), IAM, Glue DB + crawler, Athena workgroup, Lambda functions, Bedrock Guardrail (+version), Knowledge Base (+data source `schema-docs/approved/`, no chunking), Agent, action group, alias, vector store + policies. Verified resource names: `aws_bedrockagent_*`, `aws_bedrock_guardrail`, `aws_opensearchserverless_*` — I will confirm exact schemas against the pinned provider docs in Phase 1 before writing code.
- **Python scripts** (run locally, never deployed): `bootstrap_state.py`, `prepare_and_upload_data.py`, `create_vector_index.py`, `refresh.py`, `smoke_test_agent.py`, `run_evaluation.py`.
- **Lambda code** (built via `make build`, deployed by Terraform with `source_code_hash`): `src/action_group/`, `src/doc_builder/`, plus shared `src/common/`.

### 2.5 Repo structure
As specified in the brief (terraform modules + envs, src/, scripts/, glossary/, tests/, Makefile, README, PLAN, `.pre-commit-config.yaml`). Justification for keeping it: it cleanly separates deployable Lambda code from local orchestration scripts and reusable modules from env wiring. I'll add `.gitignore` (data, `dist/`, `build/`, `*.zip`, `.terraform/`, `*.tfstate*`, venv) and a `make deploy` target that runs `make build` first (per your note).

### 2.6 Security posture (non-negotiable, implemented in later phases)
- CMK for S3 + Lambda env vars; S3 public-access block, versioning, TLS-only policy, lifecycle rules.
- Least-privilege IAM per role; `aws:SourceArn` + `aws:SourceAccount` on service trust. Bedrock agent roles follow AWS naming/trust requirements (verified).
- Action-group Lambda: **read-only on the lake**, write only to the Athena results prefix, **no Glue write actions** (defense-in-depth behind the validator).
- `sqlglot` validator (Athena dialect): one statement, SELECT root (CTEs allowed), no DDL/DML, table allow-list from Glue DB, no `information_schema`/system tables, enforced `LIMIT`, max query length. Unit-tested against stacked statements, comment-hidden keywords, `UNION` into other tables, CTAS.
- Retrieved docs + query results treated as untrusted text; agent instructions say to ignore in-data instructions.
- Athena workgroup: enforced config, encrypted results, per-query bytes-scanned limit. Lambda timeouts + reserved concurrency on action-group Lambda.

### 2.7 Bedrock specifics
- Embeddings: **Amazon Titan Text Embeddings v2**. KB data source `schema-docs/approved/`, no chunking (1 table = 1 doc). Guardrail: PII masking + denied off-topic + prompt-attack filtering, attached via published version. Agent instructions in a versioned file (call `get_schema_context` first, database-qualified names, never invent columns, state when schema can't answer, always show SQL). Self-correction: clear short error so the agent retries up to 3×.

### 2.8 Evaluation
`golden_set.yaml` (≥30 questions over credit-card data with expected SQL, + off-topic/unsafe refusals). `run_evaluation.py` reports execution rate + result-set accuracy + refusal correctness; exits non-zero below thresholds (release gate).

---

## 3. Questions I need answered before Phase 1

1. **Credentials** — The terminal is currently an IAM *user* `Admin` with long-lived keys, not SSO. Do you want me to (a) proceed using this existing `Admin` identity, or (b) set up/point me at an SSO profile (`aws sso login --profile ...`)? *(I recommend b, and at minimum a scoped deployment role rather than the account-root `Admin` user.)*
2. **Region** — default `us-east-1` (has Bedrock Agents, KBs, Titan Embeddings v2, and the Claude models). OK to use `us-east-1`?
3. **Project name** — used as the `<project>-<env>-<component>` prefix and bucket names. I propose **`text2sql`** (e.g. `text2sql-dev-lake`). Acceptable?
4. **Model ID** — the agent's Claude model. I propose a **Claude Sonnet-class** model as default (good SQL reasoning vs cost). I'll verify the exact current Bedrock ID/`inference profile` with the AWS CLI in Phase 1 and report it before wiring. Accept Sonnet as the target?
5. **Vector store** — the big one. **Aurora Serverless v2 pgvector (near-zero idle, needs VPC)** vs **OpenSearch Serverless (~$345/mo baseline, no VPC)** vs a partner store. See §2.3. My recommendation: Aurora pgvector for `dev`, OpenSearch Serverless for `prod`. Which do you want?
6. **Environments** — `dev` + `prod` (prod wired in Phase 5). Confirm, or dev-only for now?

---

## 4. Cost estimate (us-east-1, dev environment, low usage)

| Component | Est. monthly |
|---|---|
| S3 (lake + docs + artifacts, ~350 MB) | < $0.05 |
| Glue Data Catalog + crawler (1 table) | ≈ $0 (free tier) |
| Athena (small scans, capped) | < $0.10 |
| **Vector store** | **≈ $0–5 (Aurora pgvector) or ~$345 (OpenSearch Serverless)** |
| Bedrock (agent + embeddings + guardrail, dev traffic) | < $5 |
| Lambda (low invocations) | ≈ $0 (free tier) |
| KMS (2–3 CMKs) | ≈ $3 |
| CloudWatch Logs | ≈ $0 |
| **Total dev** | **≈ $8–15 (Aurora) vs ~$355 (OpenSearch)** |

Prices are approximate and change; the vector store is the only material line.

---

## 5. Risks

1. **Credentials**: `Admin` IAM user + long-lived keys contradict the security bar; needs your decision (Q1).
2. **PII**: dataset contains PII-shaped fields. Mitigated by Guardrail masking + read-only lake role + glossary documentation, but worth your sign-off on keeping them in the lake vs. redacting at load.
3. **Bedrock resource schemas drift**: `aws_bedrockagent_*` / `aws_bedrock_guardrail` change between provider versions; I will pin a provider and verify against docs before Phase 1 code.
4. **OpenSearch policy propagation delay**: vector index must exist before the KB; `create_vector_index.py` handles the retry window.
5. **Model/region availability**: must be verified with AWS CLI before writing Bedrock code (done in Phase 1).
6. **Working directory has spaces + double-space** in its name; harmless for Terraform but can bite some tooling. If it causes friction I'll suggest a clean path.

---

## 6. Phase plan (approval gates at each)

- **Phase 1** (foundation): scaffold + tooling + pre-commit + git init, state bootstrap, KMS, storage module, `envs/dev` skeleton.
- **Phase 2** (data lake): data prep/upload, Glue DB + crawler, Athena workgroup; run crawler + prove with an Athena query.
- **Phase 3** (metadata + KB): doc builder + extractor interface (`glue.py` implemented, `oracle.py` stub), glossary, vector store, KB, `refresh.py`, first ingestion; prove retrieval with `retrieve` on 5 questions.
- **Phase 4** (agent): guardrail, action-group Lambda + validator, agent + alias; prove with `smoke_test_agent.py`.
- **Phase 5** (eval + hardening): golden-set evaluation, security scans (`tfsec`/`checkov`), test refresh with a new column/table, `envs/prod`, README.
- **Phase 6** (optional, on request only): second dataset, Oracle extractor, UI, monitoring/automation.

---

**STOPPING HERE for your approval.** Please answer the six questions (or say "use your defaults" and I'll proceed with: us-east-1, project `text2sql`, Claude Sonnet-class, **Aurora pgvector for dev**, dev+prod, and I'll flag the credentials choice for you to confirm).
