# PLAN: Model Routing Efficiency Lab

## Context

Build a small Python 3.11 FastAPI application that compares the same prompt
across:

1. A locally hosted Foundry Local Qwen endpoint implementing OpenAI-compatible
   `POST /v1/chat/completions`.
2. An Azure OpenAI endpoint.

The application will expose an OpenAI-compatible routing endpoint and a
server-rendered comparison dashboard. It will record measurements as JSON
Lines and use Azure OpenAI as an automated quality judge.

This plan follows an explore-plan-execute-verify workflow. Application
implementation must not begin until this plan is approved.

## Decisions

- Stack: FastAPI, Jinja templates, `httpx`, Pydantic, Python 3.11+.
- Interface: OpenAI-compatible proxy plus server-rendered dashboard.
- Comparison: Send one prompt concurrently to Qwen and Azure OpenAI.
- Persistence: Append-only JSONL in a local `data/` directory.
- Judge: Azure OpenAI returns structured quality scores.
- Default privacy: Persist prompt/response hashes and metrics, not content.
- Scope: Non-streaming public text responses in v1. Provider adapters use
  streaming internally to capture time to first token and decode throughput.

## Proposed Structure

```text
src/model_router/
  app.py
  config.py
  models.py
  routing.py
  metrics.py
  storage.py
  providers/
    base.py
    openai_chat_completions.py
  judging/
    azure_judge.py
  templates/
    index.html
    comparison.html
tests/
  unit/
  integration/
data/
  .gitkeep
pyproject.toml
.env.example
.gitignore
```

## Public Interfaces

### `POST /v1/responses`

Accept the supported, non-streaming subset of the OpenAI Responses request.
Translate it into Chat Completions messages, then route one request according
to a configured model alias:

- `qwen/<model>` routes to the local OpenAI-compatible endpoint.
- `azure/<deployment>` routes to Azure OpenAI.

Consume the upstream streaming response, normalize it into an OpenAI
Responses-compatible result, and record metrics. Client-facing streaming is
outside v1.

### `POST /api/comparisons`

Accept a prompt and selected Qwen/Azure model names. Call both providers
concurrently, judge both responses in one Azure judge request, persist the
measurement record, and return both results and computed metrics.

Partial provider failure must remain visible: return the successful result and
an explicit error for the failed provider. Do not fabricate usage or scores.

### Dashboard

- Prompt form with Qwen and Azure model/deployment selectors.
- Side-by-side escaped response text.
- Per-provider token, latency, throughput, quality, and cost metrics.
- Relative winner indicators for each metric, without declaring one universal
  winner.
- Recent metric-only comparisons loaded from JSONL.
- CSV export of metric records.

### `GET /health`

Report application health and configuration presence without revealing secret
values or making paid model calls.

## Metrics

For each candidate response, record:

- `input_tokens`, `output_tokens`, and `total_tokens` from provider usage.
- End-to-end wall-clock latency in milliseconds.
- Time to first token in milliseconds.
- Decode duration in milliseconds.
- Decode throughput: completion tokens divided by decode duration.
- End-to-end throughput: completion tokens divided by total latency.
- Output/input token ratio; report undefined when input tokens are zero.
- Tokens per successful request.
- Azure judge score on a documented 1-5 rubric.
- Quality per 1,000 candidate tokens:
  `judge_score * 1000 / total_tokens`.
- Estimated commercial cost using configured per-million input/output prices.
- Estimated managed-hosting allocation:
  `hourly_cost * latency_seconds / 3600`.

Judge input/output tokens, latency, and estimated cost must be recorded
separately and excluded from candidate efficiency values.

## Configuration

Document environment variables in `.env.example` without real values:

- `QWEN_BASE_URL`
- `QWEN_API_KEY` (optional for trusted local endpoints)
- `QWEN_MODEL`
- `QWEN_HOURLY_COST_USD`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_JUDGE_DEPLOYMENT`
- `AZURE_INPUT_COST_PER_MILLION`
- `AZURE_OUTPUT_COST_PER_MILLION`
- `ROUTER_DATA_DIR`
- `ROUTER_STORE_CONTENT`
- `ROUTER_API_KEY` (optional local proxy protection)

Configuration errors must identify missing variable names without exposing
other configuration or secret values.

Azure authentication uses `AZURE_OPENAI_API_KEY` when configured. Otherwise,
it uses `DefaultAzureCredential`, which supports Azure CLI login during local
development and managed identity in Azure.

## Tasks

### 1. Establish project scaffolding

- Add `pyproject.toml` with pinned-compatible runtime and development
  dependencies.
- Add package, test, template, and data directories.
- Add `.gitignore` and `.env.example`.
- Add a minimal application factory and health endpoint.
- Commit as one logical scaffolding change.

### 2. Implement typed provider adapters

- Define a provider protocol and normalized response/usage models.
- Implement streaming Chat Completions adapters for local Qwen and Azure
  OpenAI.
- Request `stream_options.include_usage=true` and read usage from the final
  stream chunk.
- Add Foundry Local model discovery through `GET /v1/models`.
- Normalize upstream chunks into a Responses-compatible result without
  estimating missing token usage.
- Preserve upstream status and diagnostic details without exposing secrets.
- Add unit tests using `httpx.MockTransport`.
- Commit adapters and tests together.

### 3. Implement routing and measurement

- Parse `qwen/` and `azure/` model aliases.
- Implement the non-streaming `/v1/responses` route.
- Measure latency and validate provider-supplied usage.
- Implement deterministic efficiency and cost calculations.
- Add unit and API tests.
- Commit routing, metrics, and tests together.

### 4. Implement comparison and judging

- Fan out one prompt to both providers concurrently.
- Ask Azure OpenAI to score both responses in one structured judge call.
- Define a stable 1-5 rubric covering correctness, relevance, and completeness.
- Keep judge usage separate from candidate usage.
- Preserve partial successes and surface judge failures explicitly.
- Add tests for success, partial failure, malformed judge output, and timeout.
- Commit comparison, judge, and tests together.

### 5. Implement JSONL persistence and export

- Define a versioned record schema.
- Append records safely for the documented single-process v1 runtime.
- Tolerate a truncated final line while surfacing other malformed records.
- Default to hashes instead of persisted prompt/response content.
- Add metric-only history and CSV export.
- Add persistence, privacy, and malformed-data tests.
- Commit persistence and tests together.

### 6. Implement the dashboard

- Add server-rendered prompt and result pages.
- Escape all model output.
- Display formulas, units, missing metrics, and partial failures clearly.
- Add recent comparisons and CSV export links.
- Add FastAPI integration tests for rendering and form submission.
- Commit dashboard and tests together.

### 7. Add documentation and CI

- Document setup, configuration, run, test, and security guidance.
- Document metric definitions and cost-estimate limitations.
- Add CI for tests, Ruff, and mypy with pinned action revisions.
- Keep live endpoint checks opt-in and excluded from pull-request CI.
- Commit documentation and CI together.

### 8. Verify against the plan

- Run `pytest`.
- Run `ruff check .` and `ruff format --check .`.
- Run `mypy src`.
- Run `gh aw validate`.
- Start the server and verify `/health`.
- Run an opt-in live comparison only when endpoint variables are configured.
- Inspect JSONL and CSV output for secrets and content-retention behavior.
- Review the final diff against every task and success criterion.

## Risks and Tradeoffs

- Provider tokenizers may count the same prompt differently; present provider
  usage as authoritative rather than claiming tokenizer parity.
- An Azure judge may favor Azure output. Show the rubric and retain raw scores;
  do not treat the judge score as objective ground truth.
- Managed cost derived from request duration ignores concurrency and idle time.
  Label it as an allocation estimate and keep the formula configurable.
- JSONL is appropriate for a single-process prototype, not concurrent
  multi-worker production writes.
- OpenAI Responses compatibility will intentionally cover only the documented
  non-streaming text subset in v1.
- Persisting prompts can expose sensitive data, so content retention remains
  off by default.

## Success Criteria

- The same prompt can be compared concurrently across Qwen and Azure OpenAI.
- `/v1/responses` routes documented model aliases without changing successful
  provider response bodies.
- The dashboard reports all requested token-efficiency views, latency,
  estimated cost, and automated quality scores.
- Candidate and judge usage are separated in API, JSONL, CSV, and UI output.
- Provider failures and missing usage are explicit; no metrics are fabricated.
- Default persistence contains no API keys and no raw prompt/response content.
- Unit and integration tests require no live credentials.
- Tests, lint, formatting, type checking, and workflow validation pass.
- A human reviews each implementation pull request before merge.
