# Implementation Plan: Agent Capability Upgrade

**Branch**: `003-agent-capability-upgrade` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-agent-capability-upgrade/spec.md`

## Summary

Upgrade sub-agents from single-shot LLM calls to capable workers with tool calling, dependency-aware context, self-review, and structured output. This is an **incremental upgrade** to the existing AgentsTeam system — all changes are additive, backward-compatible, and opt-in per agent role.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLModel, aiosqlite, httpx (for tool HTTP calls), anthropic SDK, openai SDK
**Storage**: SQLite via SQLModel + aiosqlite (existing)
**Testing**: pytest + pytest-asyncio
**Target Platform**: macOS (local single-user service)
**Project Type**: Existing web service — incremental feature addition
**Performance Goals**: Tool calls complete in <30s each, self-review adds <15s latency, dependency injection adds <100ms
**Constraints**: Backward compatible with all existing agents; no DB migration needed (all new fields nullable)
**Scale/Scope**: Affects 7 existing agents, 5 core files modified, 2 new files created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> Note: The constitution was written for WorkAgent (001). AgentsTeam (002/003) is a separate project. Applicable principles evaluated below.

| Principle | Applies? | Status | Notes |
|-----------|----------|--------|-------|
| Skill-Driven Architecture | No | N/A | AgentsTeam uses Goal/Task model, not Skill-based |
| Incremental Enhancement | Yes | PASS | All changes are additive. No existing APIs broken. New fields are nullable with defaults. |
| Agent Abstraction | Yes | PASS | Tool calling extends BaseAgent uniformly. Provider-specific translation stays in adapters. |
| Resilient Execution | Yes | PASS | Tool call loops have max iterations. Tool failures are graceful. Self-review is optional. |
| Local-First | Yes | PASS | Tools use httpx for web calls. No new cloud dependencies. |
| Simplicity | Yes | PASS | 3 built-in tools (not 20). Prompt-based JSON enforcement (not provider-specific). Single review pass (not multi-round). |

**Gate result: PASS** — No violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-agent-capability-upgrade/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── internal-api.md  # Internal interface contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (next step: /speckit.tasks)
```

### Source Code (files to modify/create)

```text
AgentsTeam/
├── src/
│   ├── agents/
│   │   └── base.py              # MODIFY: tool calling loop, self-review, structured output
│   ├── core/
│   │   ├── orchestrator.py      # MODIFY: context building, dependency injection, tool message publishing
│   │   ├── scheduler.py         # MODIFY: add get_dependency_results(), fix get_task_results()
│   │   └── message_bus.py       # MODIFY: add public resolve_name()
│   ├── models/
│   │   ├── agent.py             # MODIFY: add available_tools, output_schema, enable_self_review
│   │   └── task.py              # MODIFY: add result_structured
│   ├── providers/
│   │   ├── base.py              # MODIFY: extend LLMResponse, chat() signature for tools
│   │   ├── anthropic.py         # MODIFY: translate tools to Anthropic format, parse tool_calls
│   │   ├── openai_provider.py   # MODIFY: translate tools to OpenAI format, parse tool_calls
│   │   └── local.py             # MODIFY: text-based tool fallback
│   └── tools/                   # NEW: tool system
│       ├── __init__.py           # NEW: ToolRegistry singleton
│       ├── base.py               # NEW: ToolDefinition, ToolCall, ToolResult dataclasses
│       ├── web_search.py         # NEW: web_search tool implementation
│       ├── web_fetch.py          # NEW: web_fetch tool implementation
│       └── create_artifact.py    # NEW: create_artifact tool implementation
└── tests/
    ├── test_tools.py             # NEW: tool execution tests
    └── test_agent_tools.py       # NEW: agent tool-calling loop tests
```

**Structure Decision**: New `src/tools/` package for tool system. All other changes are modifications to existing files. No structural reorganization needed.

## Complexity Tracking

No constitution violations — this section is not required.
