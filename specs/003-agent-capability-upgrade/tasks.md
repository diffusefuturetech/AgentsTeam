# Tasks: Agent Capability Upgrade

**Input**: Design documents from `/Users/jiangxinxi/Documents/code/AgentsTeam/specs/003-agent-capability-upgrade/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/internal-api.md
**Project Root**: `/Users/jiangxinxi/Documents/code/AgentsTeam/`

**Tests**: Not explicitly requested — test tasks omitted. Add via follow-up if needed.

**Organization**: Tasks grouped by user story. US1 (Tool Calling) and US2 (Context Quality) are both P1 but US2 is a prerequisite for US1's full value, so US2 is placed in Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1–US5)
- All file paths relative to project root `/Users/jiangxinxi/Documents/code/AgentsTeam/`

---

## Phase 1: Setup

**Purpose**: New package structure and shared data types

- [x] T001 Create tool system package directory `src/tools/` with `__init__.py`
- [x] T002 [P] Create tool base types (ToolDefinition, ToolCall, ToolResult dataclasses) in `src/tools/base.py`
- [x] T003 [P] Add new settings to `src/config.py`: MAX_TOOL_ITERATIONS (default 10), MAX_DEPENDENCY_RESULT_LENGTH (default 4000)

---

## Phase 2: Foundational — Context Quality (US2 merged here as prerequisite)

**Purpose**: Fix context quality issues that ALL subsequent user stories depend on. This covers US2 (Downstream Agents Receive Upstream Results) because it is a foundation for meaningful agent collaboration.

**⚠️ CRITICAL**: Tool calling and structured output depend on agents having correct context. Complete this phase first.

- [x] T004 Add public `resolve_name(role_id)` method to MessageBus in `src/core/message_bus.py` (delegates to existing `_resolve_name`)
- [x] T005 Replace UUID strings with agent names in context building: change `str(m.sender_role_id)` to `self.message_bus.resolve_name(m.sender_role_id)` in `src/core/orchestrator.py` `_execute_task()` lines 281-287
- [x] T006 Add `get_dependency_results(session, goal_id, task)` method to TaskScheduler in `src/core/scheduler.py` — fetches title, agent name, and result for each task in `depends_on`
- [x] T007 Inject dependency results into task_description in `src/core/orchestrator.py` `_execute_task()` — call `scheduler.get_dependency_results()`, append formatted results section before `agent.process_message()` call
- [x] T008 Add optional `role_name_resolver` parameter to `get_task_results()` in `src/core/scheduler.py` — resolve `assigned_to` UUID to agent name when resolver provided
- [x] T009 Pass `self.message_bus.resolve_name` as role_name_resolver in `_evaluate_goal_completion()` in `src/core/orchestrator.py`
- [x] T010 Raise message truncation limit from 2000 to 8000 chars in `src/core/orchestrator.py` `_execute_task()` line 317

**Checkpoint**: Agent context now uses human-readable names, downstream tasks receive upstream results, CEO sees agent names in evaluation

---

## Phase 3: User Story 1 — Agent Uses Tools (Priority: P1) 🎯 MVP

**Goal**: Agents can invoke tools (web_search, web_fetch, create_artifact) during task execution via a provider-native tool-calling loop

**Independent Test**: Assign a research task to Growth Hacker with `available_tools=["web_search"]`, verify tool invocation appears in observation feed and result references external data

### Data Model Changes for US1

- [x] T011 [P] [US1] Add `available_tools: Optional[List[str]]` field (JSON, nullable) to AgentRole model in `src/models/agent.py`
- [x] T012 [P] [US1] Extend LLMResponse dataclass with `tool_calls: list[ToolCall] | None = None` and `stop_reason: str | None = None` in `src/providers/base.py`
- [x] T013 [P] [US1] Extend `BaseLLMProvider.chat()` signature with optional `tools: list[ToolDefinition] | None = None` parameter in `src/providers/base.py`

### Tool Implementations for US1

- [x] T014 [P] [US1] Implement `web_search` tool (duckduckgo-search package, return top 5 results formatted) in `src/tools/web_search.py`
- [x] T015 [P] [US1] Implement `web_fetch` tool (httpx GET URL, strip HTML with basic regex, truncate to 8000 chars) in `src/tools/web_fetch.py`
- [x] T016 [P] [US1] Implement `create_artifact` tool (create Artifact DB record, return confirmation) in `src/tools/create_artifact.py`
- [x] T017 [US1] Create ToolRegistry singleton that registers all built-in tools and provides lookup by name in `src/tools/__init__.py`

### Provider Adapter Changes for US1

- [x] T018 [P] [US1] Update OpenAIProvider to translate ToolDefinition to OpenAI function format, pass `tools` param to API, parse `tool_calls` from response into ToolCall objects in `src/providers/openai_provider.py`
- [x] T019 [P] [US1] Update AnthropicProvider to translate ToolDefinition to Anthropic tool format, pass `tools` param to API, parse `tool_use` content blocks into ToolCall objects in `src/providers/anthropic.py`
- [x] T020 [P] [US1] Update LocalProvider with text-based tool fallback: include tool descriptions in system prompt, parse `[TOOL_CALL: name(args)]` from response in `src/providers/local.py`

### Agent Execution Loop for US1

- [x] T021 [US1] Implement tool-calling loop in `BaseAgent.process_message()` in `src/agents/base.py`: after LLM call, check for tool_calls → execute via ToolRegistry → append tool results to messages → re-call LLM → repeat until no tool_calls or max iterations reached
- [x] T022 [US1] Add tool execution helper method `_execute_tool_call(call: ToolCall)` to BaseAgent in `src/agents/base.py` — looks up tool in registry, calls handler, returns ToolResult
- [x] T023 [US1] Load agent's `available_tools` from role config and resolve to ToolDefinition list in BaseAgent.__init__() or process_message() in `src/agents/base.py`

### Orchestrator Integration for US1

- [x] T024 [US1] Publish tool call events as status_update messages in orchestrator observation feed — format: "🔧 Tool: {name}({args}) → ✓/✗" with metadata `{"tool_call": true}` in `src/core/orchestrator.py`
- [x] T025 [US1] Configure Growth Hacker and AI Citation Strategist predefined roles with `available_tools=["web_search", "web_fetch"]` in `src/agents/predefined/growth_hacker.py` and `src/agents/predefined/ai_citation_strategist.py`
- [x] T026 [US1] Configure Content Creator predefined role with `available_tools=["web_search", "create_artifact"]` in `src/agents/predefined/content_creator.py`

**Checkpoint**: Agents with tools configured can search the web and fetch URLs during task execution. Tool calls visible in observation feed. Agents without tools behave unchanged.

---

## Phase 4: User Story 3 — Agent Self-Reviews Output (Priority: P2)

**Goal**: Agents can optionally perform a self-review step, improving output quality

**Independent Test**: Enable self-review on an agent, assign a complex task, verify observation feed shows both draft and final output

### Implementation for US3

- [x] T027 [P] [US3] Add `enable_self_review: bool = Field(default=False)` to AgentRole model in `src/models/agent.py`
- [x] T028 [US3] Implement self-review logic in `BaseAgent.process_message()` in `src/agents/base.py`: after initial response, if `self.role.enable_self_review`, append response as assistant message + review prompt, call LLM again, return revised response
- [x] T029 [US3] Publish self-review events: publish draft as status_update ("📝 Self-review") in `src/core/orchestrator.py`

**Checkpoint**: Agents with self-review enabled produce two-pass outputs. Agents without self-review behave unchanged.

---

## Phase 5: User Story 4 — Structured Output (Priority: P2)

**Goal**: Agents with output schemas return parseable JSON for downstream consumption

**Independent Test**: Configure an agent with output_schema via API, assign a task, verify `task.result_structured` contains parsed JSON in database

### Implementation for US4

- [x] T030 [P] [US4] Add `output_schema: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))` to AgentRole model in `src/models/agent.py`
- [x] T031 [P] [US4] Add `result_structured: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))` to Task model in `src/models/task.py`
- [x] T032 [US4] Implement `_format_output_instruction()` in BaseAgent in `src/agents/base.py`: when `self.role.output_schema` is set, return prompt suffix with JSON schema requirement
- [x] T033 [US4] Implement `_parse_structured_output(raw: str)` in BaseAgent in `src/agents/base.py`: attempt json.loads, strip markdown fences, fall back to raw text on failure
- [x] T034 [US4] Integrate structured output into `process_message()` in `src/agents/base.py`: append output instruction to task, parse response, return JSON string if structured
- [x] T035 [US4] Store `result_structured` in orchestrator `_execute_task()` in `src/core/orchestrator.py`: attempt `json.loads(result)` → set `task.result_structured`

**Checkpoint**: Agents with output_schema return parseable JSON. Agents without schema behave unchanged. Failed parsing falls back gracefully.

---

## Phase 6: User Story 5 — Agent Requests Help from Another Agent (Priority: P3)

**Goal**: Agents can invoke other agents mid-task via ask_agent tool

**Independent Test**: Configure an agent with ask_agent tool, trigger a task requiring another agent's expertise, verify helper response injected into context

### Implementation for US5

- [x] T036 [US5] Implement `ask_agent` tool handler in `src/tools/ask_agent.py`: accept target_role_key and request string, dispatch to target agent via orchestrator, return result
- [x] T037 [US5] Register ask_agent tool in ToolRegistry in `src/tools/__init__.py`
- [x] T038 [US5] Add agent-to-agent request method to orchestrator: create sub-task, execute target agent's process_message, return result — with loop detection (max 3 nested calls) in `src/core/orchestrator.py`
- [x] T039 [US5] Publish agent-to-agent request events as status_update messages in observation feed in `src/core/orchestrator.py`
- [x] T040 [US5] Configure Xiaohongshu Specialist with `available_tools=["web_search", "ask_agent"]` in `src/agents/predefined/xiaohongshu_specialist.py`

**Checkpoint**: Agents can request help from other agents. Requests visible in observation feed. Loop detection prevents infinite recursion.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration validation, edge cases, documentation

- [x] T041 Delete and recreate database (`agents_team.db`) to pick up new nullable columns on AgentRole and Task models
- [ ] T042 Verify backward compatibility: start server, confirm all existing agents without tools/schema/review work identically
- [ ] T043 Run quickstart.md validation: submit goal with dependency chain, verify context quality + tool calling + observation feed
- [ ] T044 Update README.md with new agent capabilities (tools, self-review, structured output)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational/US2 (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 Tools (Phase 3)**: Depends on Phase 2 — MVP target
- **US3 Self-Review (Phase 4)**: Depends on Phase 2 — can run in parallel with Phase 3
- **US4 Structured Output (Phase 5)**: Depends on Phase 2 — can run in parallel with Phases 3-4
- **US5 Agent Collaboration (Phase 6)**: Depends on Phase 3 (needs tool system)
- **Polish (Phase 7)**: Depends on all desired phases complete

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational / US2: Context Quality)
    ↓
Phase 3 (US1: Tool Calling) ←── MVP STOP POINT
    ↓                    ↘
Phase 4 (US3: Self-Review)   Phase 5 (US4: Structured Output) ←── parallel
    ↓
Phase 6 (US5: Agent Collaboration) ←── needs US1 tool system
    ↓
Phase 7 (Polish)
```

### Within Each User Story

- Data model changes before provider changes
- Provider changes before BaseAgent changes
- BaseAgent changes before orchestrator integration
- Tool implementations can run in parallel with provider changes

### Parallel Opportunities

**Phase 1** (all parallel):
- T002, T003 can run in parallel

**Phase 2** (sequential — same files):
- T004 → T005 (message_bus then orchestrator)
- T006 → T007 (scheduler then orchestrator)
- T008 → T009 (scheduler then orchestrator)

**Phase 3** (highest parallelism):
- T011, T012, T013 (model changes) can run in parallel
- T014, T015, T016 (tool implementations) can run in parallel
- T018, T019, T020 (provider adapters) can run in parallel

**Phase 4-5** can run in parallel with Phase 3.

---

## Parallel Example: Phase 3 (Tool Calling)

```bash
# Launch all model changes in parallel:
T011: "Add available_tools to AgentRole in src/models/agent.py"
T012: "Extend LLMResponse with tool_calls in src/providers/base.py"
T013: "Extend chat() signature with tools param in src/providers/base.py"

# Launch all tool implementations in parallel:
T014: "Implement web_search in src/tools/web_search.py"
T015: "Implement web_fetch in src/tools/web_fetch.py"
T016: "Implement create_artifact in src/tools/create_artifact.py"

# Launch all provider adapters in parallel:
T018: "Update OpenAIProvider for tools in src/providers/openai_provider.py"
T019: "Update AnthropicProvider for tools in src/providers/anthropic.py"
T020: "Update LocalProvider for tools in src/providers/local.py"
```

---

## Implementation Strategy

### MVP First (Phase 1 → 2 → 3)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Context Quality (T004–T010)
3. Complete Phase 3: Tool Calling (T011–T026)
4. **STOP and VALIDATE**: Submit a research goal, verify tools fire and context is clean
5. This is a working MVP — agents have tools and good context

### Incremental Delivery

1. Setup + Context Quality → Immediate improvement in agent collaboration quality
2. Add Tool Calling → **MVP!** Agents can research and create artifacts
3. Add Self-Review → Higher quality outputs for complex tasks
4. Add Structured Output → Machine-readable results for downstream agents
5. Add Agent Collaboration → Emergent teamwork beyond CEO's initial plan
6. Polish → Documentation, edge cases, validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story from spec.md
- All file paths relative to `/Users/jiangxinxi/Documents/code/AgentsTeam/`
- T012 and T013 both modify `src/providers/base.py` — implement together despite [P] marker
- Delete `agents_team.db` after schema changes (Phase 7 T041) to pick up new columns
- Commit after each phase checkpoint
