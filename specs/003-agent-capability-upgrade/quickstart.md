# Quickstart: Agent Capability Upgrade

**Feature**: 003-agent-capability-upgrade | **Date**: 2026-03-17

## Prerequisites

- AgentsTeam already running (see project root quickstart)
- At least one LLM API key configured (OpenAI or Anthropic)
- Python virtual environment activated

## What Changes

This upgrade adds 5 capabilities to sub-agents:

1. **Tool calling** — agents can search the web, fetch URLs, and create artifacts
2. **Dependency result passing** — downstream agents automatically receive upstream results
3. **Human-readable context** — agent names instead of UUIDs in all messages
4. **Self-review** — optional quality check before submitting results
5. **Structured output** — optional JSON schema enforcement per agent

## Verification Steps

### 1. Context Quality (should work immediately)

1. Start the server: `.venv/bin/python -m src.main`
2. Open `http://localhost:9000` in browser
3. Submit a goal: "分析抖音营销趋势并制定内容策略"
4. Observe the message feed — agent names should appear (not UUIDs)
5. When the content strategy task runs, check that it references the trend analysis results

### 2. Tool Calling

1. Verify an agent has `available_tools` configured (e.g., Growth Hacker with `["web_search"]`)
2. Submit a goal requiring research: "调研竞品在抖音的营销策略"
3. Observe the message feed for tool call messages (🔧 icon)
4. The agent's final output should reference data from search results

### 3. Self-Review

1. Verify an agent has `enable_self_review: true` (e.g., CEO agent)
2. Submit a goal and observe the CEO's evaluation step
3. The observation feed should show both draft and final versions

### 4. Structured Output

1. Configure an agent with `output_schema` via the API
2. Assign a task to that agent
3. Check the database: `task.result_structured` should contain parsed JSON
4. If JSON parsing fails, `task.result` still contains the raw text (no crash)

## Configuration

New optional fields on agent roles (via API `PUT /api/agents/{id}`):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `available_tools` | list[str] | null | Tool names: "web_search", "web_fetch", "create_artifact" |
| `output_schema` | dict | null | JSON Schema for structured output |
| `enable_self_review` | bool | false | Enable self-review step |

New settings (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_TOOL_ITERATIONS` | 10 | Max tool call loops per task |
| `MAX_DEPENDENCY_RESULT_LENGTH` | 4000 | Max chars per dependency result injection |
