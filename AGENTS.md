# AGENTS.md

This file provides guidance to AI coding agents working in this repository.

## Repository Overview

**Model Routing Efficiency Lab** compares a locally hosted Qwen endpoint with
Azure OpenAI. It exposes an OpenAI-compatible proxy, a small server-rendered
dashboard, and measurements for token usage, latency, quality, and estimated
cost. The repository also contains cost-controlled GitHub Agentic Workflows.

## Project Structure

- `src/model_router/` - FastAPI application, provider adapters, metrics, and
  JSONL persistence.
- `src/model_router/templates/` - Server-rendered dashboard templates.
- `tests/unit/` - Isolated tests using mocked HTTP transports.
- `tests/integration/` - API-level tests; live provider tests must be opt-in.
- `data/` - Local JSONL measurements; ignored by Git.
- `.github/workflows/*.md` - Source agentic workflows.
- `.github/workflows/*.lock.yml` - Generated workflows; never edit manually.

## Build and Development Commands

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the project and development dependencies
python -m pip install -e ".[dev]"

# Run the application locally
uvicorn model_router.app:app --reload

# Run tests
pytest

# Lint and format checks
ruff check .
ruff format --check .

# Type checking
mypy src

# Validate agentic workflows
gh aw validate
```

**Language/Runtime Version:** Python 3.11+

## Code Conventions

- Keep provider-specific request and response handling behind typed adapter
  interfaces.
- Use Pydantic models at API and persistence boundaries.
- Inject HTTP clients and clocks so tests do not make live network calls.
- Keep metric calculations deterministic and independent from transport code.
- Use `async` for endpoint calls and run comparison requests concurrently.
- Return explicit errors for invalid configuration and provider failures.

## Domain Context

- **Candidate tokens:** Input and output tokens consumed by the Qwen or Azure
  response being compared.
- **Judge tokens:** Tokens consumed by Azure OpenAI to score response quality.
  Track them separately and exclude them from candidate token efficiency.
- **Token efficiency:** Report output/input ratio, successful-request tokens,
  quality score per total candidate token, end-to-end throughput, and decode
  throughput.
- **Decode throughput:** Provider completion tokens divided by the time from
  the first content token until the stream completes.
- **Managed cost:** Estimate from configured hourly hosting cost multiplied by
  request duration. State that this is an allocation estimate.
- **Commercial cost:** Estimate from configured input/output token prices.

## Security and Privacy

- Read secrets only from environment variables.
- Never log or persist API keys, authorization headers, or full environment
  dumps.
- Do not persist prompt or response content by default; store hashes and
  metrics unless content retention is explicitly enabled.
- Bind the development server to loopback by default.
- Treat model output as untrusted text and escape it in HTML.

## Testing

- Unit tests must not require live endpoints or credentials.
- Use injected `httpx` transports for provider response and failure cases.
- Cover token accounting, metric formulas, JSONL writes, redaction, routing,
  comparison fan-out, judge failures, and partial provider failures.
- Live endpoint tests must require an explicit marker and environment flag.

## Agentic Workflow Conventions

- Never edit `.lock.yml` workflow files manually.
- After changing a workflow source, run `gh aw compile <workflow.md>`.
- Do not broaden workflow permissions, safe outputs, models, or cost caps
  unless the issue explicitly requires it.

## Anti-Patterns

- Do not hardcode endpoint URLs, deployments, prices, or credentials.
- Do not silently substitute fake token counts or quality scores.
- Do not estimate token usage when provider usage is missing in benchmark mode.
- Do not mix judge usage into candidate efficiency calculations.
- Do not add a database, frontend build system, or routing framework in v1.
- Do not auto-merge agent-created pull requests.

## Environment

- Primary development platform: macOS.
- Default shell: zsh/Bash-compatible commands.
- Use `/` path separators and `python3` to create the virtual environment.
