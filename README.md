# gh-aw cost-control lab

This repository is a small lab for cost-controlled GitHub Agentic Workflows. It
shows how Copilot-powered workflows can use bounded turns, AI-credit caps, and
safe outputs without requiring contributors to read generated workflow locks.

## Prerequisites

From the repository root, make sure you have:

- GitHub CLI installed and authenticated: `gh auth status`
- The `gh-aw` extension or binary available: `gh aw version`
- Actions access for `sramayanam/gh-aw-cost-lab`
- Copilot access for running Copilot-backed agentic workflows

Check repository setup before running workflows:

```bash
gh aw doctor --repo sramayanam/gh-aw-cost-lab
```

## Quickstart

1. Inspect the source workflows:

   ```bash
   gh aw list
   ```

2. Edit only source workflow Markdown files under `.github/workflows/*.md`.
   The matching `.github/workflows/*.lock.yml` files are generated; do not edit
   lock files by hand.

3. Compile the current workflows:

   ```bash
   gh aw compile
   ```

4. Validate and lint the generated workflows:

   ```bash
   gh aw validate
   gh aw lint
   ```

5. Preview or run the weekly digest workflow:

   ```bash
   gh aw run cost-lab-digest --dry-run
   gh aw run cost-lab-digest
   ```

6. Preview issue triage against an issue context. The `issue-triage` workflow is
   normally triggered when an issue is opened or reopened, so use trial mode for
   a safe preview. This authenticated example requires a real issue number:

   ```bash
   gh aw trial ./.github/workflows/issue-triage.md \
     --logical-repo sramayanam/gh-aw-cost-lab \
     --trigger-context https://github.com/sramayanam/gh-aw-cost-lab/issues/<issue-number> \
     --dry-run -y
   ```

7. Inspect recent logs and AI-credit usage without writing artifacts into the
   repository:

   ```bash
   gh aw logs cost-lab-digest issue-triage --count 1 --artifacts usage \
     --output /tmp/gh-aw-cost-lab-logs
   gh aw forecast cost-lab-digest issue-triage --period week --days 7
   gh aw audit <run-id-or-url> --output /tmp/gh-aw-cost-lab-audit
   ```

8. View safe-output outcomes for a completed run:

   ```bash
   gh aw outcomes <run-id> --repo sramayanam/gh-aw-cost-lab
   ```

## Security

Never commit personal access tokens, API keys, `.env` files, local token files,
or copied credential output. Use GitHub Actions secrets or the supported `gh aw`
configuration commands instead of storing credentials in the repository.
