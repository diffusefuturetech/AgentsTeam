# Data Model: Agent Capability Upgrade

**Feature**: 003-agent-capability-upgrade | **Date**: 2026-03-17

## Entity Changes Overview

This feature extends existing entities and adds new ones. All changes are additive (nullable columns or new tables) — no destructive migrations.

```
AgentRole (extended)          ToolDefinition (new)
├── + available_tools []  ────→ name, description, parameters
├── + output_schema {}
├── + enable_self_review bool ToolCall (new, in-memory)
                              ├── id, name, arguments
Task (extended)               └── result
├── + result_structured {}
                              ToolRegistry (new, singleton)
                              └── tools: dict[str, ToolDefinition]
```

## Extended Entities

### AgentRole (extended)

Three new nullable fields added to the existing `agentrole` table.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| available_tools | list[str] | nullable, JSON | Tool names this agent can use. e.g., ["web_search", "web_fetch"]. None = no tools. |
| output_schema | dict | nullable, JSON | JSON Schema defining expected output format. None = free-form text. |
| enable_self_review | bool | default False | Whether agent performs a self-review step after initial output. |

**Validation**:
- `available_tools` entries must exist in the ToolRegistry
- `output_schema` must be valid JSON Schema (if provided)
- All three fields are optional — existing agents work unchanged

### Task (extended)

One new nullable field added to the existing `task` table.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| result_structured | dict | nullable, JSON | Parsed JSON result when agent has output_schema. None if raw text or parsing failed. |

**Validation**:
- Only populated when the agent's `output_schema` is defined AND the LLM returns valid JSON
- Always accompanied by `result` (raw text) — `result_structured` is a convenience, not a replacement

## New Entities

### ToolDefinition

Defines a callable tool available to agents. Registered in-memory at startup (not in DB).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| name | str | unique, required | Tool identifier. e.g., "web_search" |
| description | str | required | Human-readable description for LLM consumption |
| parameters | dict | required | JSON Schema describing the tool's input parameters |
| handler | callable | required | Async function `(args: dict) -> str` that executes the tool |

**Not stored in DB** — tools are defined in code and registered at startup. This keeps tool implementations versioned with code.

### ToolCall (in-memory only)

Represents a single tool invocation during agent execution. Part of LLMResponse.

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique call ID (from LLM response) |
| name | str | Tool name being called |
| arguments | dict | Parsed arguments for the tool |

### ToolResult (in-memory only)

Result of executing a tool call.

| Field | Type | Description |
|-------|------|-------------|
| call_id | str | Matches the ToolCall.id |
| content | str | Tool execution result as text |
| is_error | bool | Whether the tool execution failed |

## LLM Interface Changes

### LLMResponse (extended)

| Field | Type | Change | Description |
|-------|------|--------|-------------|
| tool_calls | list[ToolCall] | **new**, nullable | Tool calls requested by the LLM. None if no tools invoked. |
| stop_reason | str | **new**, nullable | Why the LLM stopped: "end_turn", "tool_use", etc. |

### BaseLLMProvider.chat() (extended signature)

| Parameter | Type | Change | Description |
|-----------|------|--------|-------------|
| tools | list[ToolDefinition] | **new**, default None | Available tools for this call |

Existing calls without `tools` parameter continue to work unchanged.

## State Transitions

### Agent Execution Flow (new)

```
start
  ↓
LLM call (with tools if available)
  ↓
tool_use? ──yes──→ execute tool(s) → append results → LLM call again
  │                                                          ↑
  no / max_iterations reached                                │
  ↓                                                    loop ─┘
initial_response
  ↓
self_review enabled? ──yes──→ review LLM call → revised_response
  │
  no
  ↓
output_schema? ──yes──→ parse JSON → result_structured
  │
  no
  ↓
store result → publish → done
```

## Indexes

No new indexes required. Existing indexes on `Task.goal_id` and `Task.status` cover the dependency result queries.
