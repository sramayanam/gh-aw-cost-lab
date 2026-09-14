---
description: Manual airlines MCP tool-call smoke test

on:
  workflow_dispatch:

permissions:
  contents: read

engine:
  id: copilot
  model: gpt-5.4

timeout-minutes: 10
max-turns: 8
max-ai-credits: 150

mcp-servers:
  airlines:
    type: http
    url: https://ca-enhanced-postgresq-ypewwm.blackcoast-921fa27d.eastus2.azurecontainerapps.io/mcp

safe-outputs:
  noop:
---

## Airlines MCP Smoke Test

Use the `airlines` MCP server to make read-only, real-world database tool calls
against the airlines PostgreSQL data source.

## Instructions

1. Run `airlines --help` to discover the available tools and accepted inputs.
2. Make at least three read-only tool calls:
   - one schema or table-discovery call,
   - one targeted airline lookup,
   - one aggregate query over airline, airport, route, or flight data.
3. Do not run DDL, DML, destructive, mutation, export, or credential-discovery
   queries.
4. Produce a concise Markdown metrics report with:
   - total tool calls attempted,
   - successful tool calls,
   - failed tool calls,
   - elapsed time when observable,
   - result row counts when available,
   - two or three sample facts from the query results.
5. If the MCP server or database is unavailable, report the exact connection or
   tool error and stop without fabricating metrics.
