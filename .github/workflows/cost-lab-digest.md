---
description: Weekly repo digest, deliberately cheap

on:
  schedule: weekly
  workflow_dispatch:

permissions:
  contents: read
  issues: read
  pull-requests: read

engine:
  id: copilot
  model: gpt-5-mini

timeout-minutes: 10
max-turns: 8
max-ai-credits: 150

safe-outputs:
  create-issue:
    title-prefix: "[cost-lab] "
    labels: [report]
---

## Weekly Repo Digest

Summarize repository activity from the past 7 days as a GitHub issue.

## What to include

- Issues opened and closed
- Pull requests merged
- Notable code changes

Keep the report under 300 words. Do not read entire files — use listings and
metadata only.