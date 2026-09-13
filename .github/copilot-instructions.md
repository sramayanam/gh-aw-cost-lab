# Repository instructions

This repository demonstrates cost-controlled GitHub Agentic Workflows. Keep
changes small, reviewable, and limited to the assigned issue.

## Workflow conventions

- Treat `.github/workflows/*.md` as the source for agentic workflows.
- Never edit generated `.github/workflows/*.lock.yml` files manually.
- After changing an agentic workflow, run `gh aw compile <workflow.md>`.
- Validate workflow changes with `gh aw validate` and `gh aw lint`.
- Do not change workflow permissions, safe-output boundaries, cost caps, or
  models unless the issue explicitly requires it.

## Documentation conventions

- Use concise Markdown with commands that work from the repository root.
- Prefer existing repository commands and supported `gh-aw` syntax.
- Clearly distinguish source workflow files from generated lock files.
- Do not claim that a command was tested unless it was actually run.

## Security and scope

- Never read, print, commit, or embed credentials, tokens, or API keys.
- Do not add dependencies for documentation-only work.
- Do not modify unrelated files.
- Do not merge pull requests; leave all changes for human review.

## Validation

For documentation-only changes, verify referenced paths and run each safe,
read-only command needed to confirm the documented syntax. For workflow
changes, run:

```bash
gh aw validate
gh aw lint
```
