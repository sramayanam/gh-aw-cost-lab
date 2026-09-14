# Local vs. Commercial AI Demo Runbook

This repository compares a local Foundry Local Qwen model with Azure OpenAI
under controlled sampling conditions. It measures token usage, output length,
latency, time to first token, completion behavior, quality, and
quality-per-token.

The executive presentation is available at:

- [Local vs. Commercial AI — CIO Briefing](output/local-vs-commercial-ai-cio-briefing.html)

## Recommended CIO Demo Flow

Allow approximately 10–15 minutes:

1. Verify Foundry Local and Azure authentication.
2. Show the controlled benchmark configuration.
3. Optionally run one full live benchmark profile.
4. Inspect the metric-only aggregate report.
5. Present the executive slide deck.

The live baseline performs five local candidate calls, five Azure candidate
calls, and five Azure judge calls. It typically takes about one minute and
incurs Azure OpenAI usage.

## 1. Open the Project

```bash
git clone https://github.com/sramayanam/gh-aw-cost-lab.git
cd gh-aw-cost-lab
```

If the repository is already cloned, run only the `cd` command from its parent
directory.

## 2. One-Time Python Setup

Skip the virtual-environment creation if `.venv` already exists.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Create the local configuration only if `.env` does not already exist:

```bash
cp .env.example .env
```

Do not overwrite an existing `.env`. It contains the endpoint and model
selection for the demo and is ignored by Git.

Load the configuration into the current shell:

```bash
set -a
source .env
set +a
```

## 3. Start and Verify Foundry Local

Start the local daemon:

```bash
foundry server start
```

Load the configured model:

```bash
foundry model load "$QWEN_MODEL"
```

Verify the server and model:

```bash
foundry server status
curl --silent --show-error --fail "$QWEN_BASE_URL/models" | python -m json.tool
```

Expected model ID:

```text
qwen3.5-4b-generic-gpu
```

Inspect the packaged model metadata:

```bash
foundry model info "$QWEN_MODEL"
```

## 4. Authenticate and Verify Azure OpenAI

Sign in if needed:

```bash
az login
```

Confirm the active identity and subscription:

```bash
az account show \
  --query '{subscription:name,user:user.name,tenantId:tenantId}' \
  --output table
```

The application uses `DefaultAzureCredential`. When
`AZURE_OPENAI_API_KEY` is empty, the local Azure CLI login supplies the access
token.

Verify the Azure OpenAI v1 endpoint:

```bash
az rest \
  --method get \
  --resource https://cognitiveservices.azure.com \
  --url "$AZURE_OPENAI_ENDPOINT/models" \
  --query "data[?id=='$AZURE_OPENAI_DEPLOYMENT'].id" \
  --output table
```

Expected deployment:

```text
gpt-4.1-mini
```

Expected judge deployment:

```text
gpt-5.4
```

## 5. Run Local Validation

Run the unit tests and static checks before the meeting:

```bash
.venv/bin/pytest tests/unit
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src scripts
```

Expected result:

```text
18 tests passed
All checks passed
Success: no issues found
```

## 6. Run the Controlled Baseline

The baseline sends identical prompts to both providers with:

- `temperature=0`
- `max_tokens=1000`
- no client stop sequence
- identical user prompts

Run it with:

```bash
.venv/bin/python scripts/run_benchmark.py --profile baseline
```

The benchmark writes a metric-only report to:

```text
data/benchmark-baseline.json
```

It does not persist prompt or response text.

Inspect the executive aggregate:

```bash
jq '.sampling, .aggregate' data/benchmark-baseline.json
```

Inspect completion reasons:

```bash
jq '[
  .cases[] |
  {
    case,
    qwen_finish: .qwen.finish_reason,
    azure_finish: .azure.finish_reason
  }
]' data/benchmark-baseline.json
```

## 7. Optional Tuning Demonstrations

### Matched stop-sequence experiment

Both providers receive the same hard-format instruction and `</final>` stop
sequence:

```bash
.venv/bin/python scripts/run_benchmark.py --profile matched-stop
jq '.sampling, .aggregate' data/benchmark-matched-stop.json
```

### Matched concise-prompt experiment

Both providers receive the same brevity instruction and example:

```bash
.venv/bin/python scripts/run_benchmark.py --profile matched-concise
jq '.sampling, .aggregate' data/benchmark-matched-concise.json
```

### Qwen-specific no-thinking experiment

This is intentionally not an identical-prompt comparison. It tests Qwen
provider-specific tuning:

```bash
.venv/bin/python scripts/run_benchmark.py --profile qwen-no-thinking
jq '.sampling, .aggregate' data/benchmark-qwen-no-thinking.json
```

## 8. Expected Baseline Talking Points

The current controlled baseline produced:

- Qwen: 4,498 total candidate tokens.
- Azure: 812 total candidate tokens.
- Qwen generated 5.5 times as many total tokens.
- Qwen generated 5.7 times as many words.
- Qwen generated 6.8 times as many characters.
- Qwen average time to first token: approximately 178 ms.
- Azure average time to first token: approximately 2,453 ms.
- Qwen average quality: 4.1 out of 5.
- Azure average quality: 4.9 out of 5.
- Qwen reached the 1,000-token limit in three of five cases.
- Azure completed naturally in all five cases.

The defensible headline is:

> Under identical sampling conditions, the local Qwen 3.5 4B deployment
> produced 5.5 times as many total tokens and 5.7 times as many words while
> receiving a lower mean quality score. Three of five Qwen responses were
> truncated, so the measured verbosity difference is a lower bound.

Do not present the quality-per-token ratio without also presenting the raw
quality scores.

## 9. Open the CIO Presentation

Open the full deck on macOS:

```bash
open output/local-vs-commercial-ai-cio-briefing.html
```

Open a specific slide directly:

```bash
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=4"
```

Useful slide links:

```bash
# Executive recommendation
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=2"

# Controlled methodology
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=3"

# Tokenizer-neutral evidence
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=4"

# Truncation caveat
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=5"

# Recommended hybrid architecture
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=10"

# CIO decision
open "file://$PWD/output/local-vs-commercial-ai-cio-briefing.html?slide=11"
```

Presentation controls:

- Right Arrow, Down Arrow, Page Down, or Space: next slide.
- Left Arrow, Up Arrow, or Page Up: previous slide.
- Home: first slide.
- End: final slide.
- Navigation dots: jump directly to a slide.

## 10. Demo Recovery Commands

### Foundry Local is unavailable

```bash
foundry server status
foundry server logs
foundry server restart
foundry model load "$QWEN_MODEL"
curl --silent --show-error --fail "$QWEN_BASE_URL/models"
```

### Azure authentication fails

```bash
az login
az account show
az account get-access-token \
  --resource https://cognitiveservices.azure.com \
  --query expiresOn \
  --output tsv
```

Then rerun the Azure endpoint verification command from section 4.

### Python dependencies are missing

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### A benchmark run fails midway

The benchmark replaces its report only after all cases finish. Fix the endpoint
problem and rerun the same profile:

```bash
.venv/bin/python scripts/run_benchmark.py --profile baseline
```

## 11. After the Demo

Foundry Local can remain running for development. To stop it:

```bash
foundry server stop
```

Check that no local configuration or generated report was staged:

```bash
git status --short
```

The `.env` file and `data/` benchmark reports are intentionally ignored by
Git.

## Important Limitations

- The benchmark contains five synthetic cases; it is directional, not a
  production forecast.
- Azure `gpt-4.1-mini` is the commercial candidate and Azure `gpt-5.4` is the
  blinded judge, so residual model-family bias is possible.
- Tokenizers differ, which is why the report also compares words and
  characters.
- Cost rates are currently zero in `.env`; the demo makes no dollar-savings
  claim.
- Automated judging used more tokens than the candidate calls. Production
  judging should sample requests rather than score every response.
