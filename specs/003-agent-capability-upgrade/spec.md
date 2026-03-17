# Feature Specification: Agent Capability Upgrade

**Feature Branch**: `003-agent-capability-upgrade`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "当前每个子Agent本质上是一次性LLM调用（base.py:24-48）：拼prompt → 调API → 返回文本。没有工具、没有迭代、没有验证。需要给Agent加工具能力、多步推理与自我修正、上下文质量优化、结构化输出、以及Agent间按需协作能力。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Uses Tools to Gather Real Information (Priority: P1)

A user sets a goal like "Research and create a Douyin marketing strategy for our product". The Growth Hacker agent, instead of generating purely from memory, uses web search tools to find current competitor data, trending topics, and platform algorithm updates. The AI Citation Strategist queries actual AI engines to check citation status. The Content Creator searches for trending hashtags and formats. Each agent enriches its output with real, verifiable information gathered through tools.

**Why this priority**: This is the single highest-impact improvement. Without tools, agents are limited to LLM knowledge cutoff data and hallucinate specifics. Tool calling transforms agents from "text generators" into "research-capable workers" that produce actionable, grounded output.

**Independent Test**: Can be tested by assigning a task to any agent with tools enabled, verifying the agent invokes at least one tool during execution, and the final output references real data obtained through tool calls.

**Acceptance Scenarios**:

1. **Given** an agent has tool capabilities configured, **When** the agent receives a task requiring external information (e.g., "find current Douyin trending topics"), **Then** the agent invokes the web_search tool, receives results, and incorporates them into its response.
2. **Given** an agent invokes a tool that returns results, **When** the tool execution completes, **Then** the tool result is added to the agent's message history and the agent continues reasoning with that information.
3. **Given** an agent's tool call fails (timeout, network error), **When** the failure is detected, **Then** the agent gracefully falls back to LLM-only reasoning and notes the limitation in its output.
4. **Given** a task does not require external information, **When** the agent processes the task, **Then** the agent may choose not to invoke any tools and respond directly (tools are optional, not mandatory).

---

### User Story 2 - Downstream Agents Receive Upstream Results (Priority: P1)

When a goal is decomposed into dependent tasks (e.g., Task A: "Analyze market trends" → Task B: "Create content strategy based on analysis"), the agent working on Task B receives the complete results from Task A as structured context. The agent does not need to guess or reconstruct what the upstream agent produced.

**Why this priority**: This is the foundation of meaningful multi-agent collaboration. Without explicit result passing, task dependencies are cosmetic — they control execution order but not information flow. This directly impacts output quality for any multi-step goal.

**Independent Test**: Can be tested by creating a goal with two tasks where Task B depends on Task A, verifying that Task B's agent receives Task A's full result in its input context.

**Acceptance Scenarios**:

1. **Given** Task B depends on Task A (via depends_on), **When** Task B begins execution, **Then** Task B's agent receives Task A's complete result (title + output) as part of its task description.
2. **Given** Task B depends on multiple upstream tasks (A and C), **When** Task B begins execution, **Then** all dependency results are included, ordered by dependency index.
3. **Given** an upstream task's result exceeds the context limit, **When** the result is injected, **Then** it is truncated to a configurable maximum with a note indicating truncation.
4. **Given** an agent reviews the observation feed, **When** context messages appear, **Then** agent names (not UUIDs) are displayed as message senders.

---

### User Story 3 - Agent Self-Reviews Output Before Submission (Priority: P2)

After generating an initial response, the agent performs a self-review step: it re-reads its own output and checks it against quality criteria (completeness, actionability, relevance to the task). If the review identifies issues, the agent revises its output before submitting the final result. The user can see both the draft and final output in the observation view.

**Why this priority**: Multi-step reasoning significantly improves output quality but is less critical than tools and context quality. It can be added after the core execution pipeline is solid.

**Independent Test**: Can be tested by assigning a complex task to an agent with self-review enabled, verifying the agent produces an initial draft, performs a review, and submits a revised final output.

**Acceptance Scenarios**:

1. **Given** an agent has self-review enabled, **When** it completes the initial response, **Then** it automatically performs a review step evaluating completeness, actionability, and task relevance.
2. **Given** the review step identifies issues, **When** the agent revises its output, **Then** the final submitted result reflects the improvements.
3. **Given** the review step finds no issues, **When** the review completes, **Then** the original output is submitted without unnecessary modification.
4. **Given** a task is simple or time-sensitive, **When** the agent is configured without self-review, **Then** it behaves as a single-shot agent (backward compatible).

---

### User Story 4 - Agents Return Structured Output (Priority: P2)

Different agents return results in formats appropriate to their role. A Growth Hacker returns a structured experiment plan (hypothesis, metrics, actions), a Content Creator returns structured content (title, body, platform, keywords, CTA), and a Douyin Strategist returns a video content plan (hook, script beats, hashtags, posting schedule). The CEO agent can parse these structured results for better evaluation.

**Why this priority**: Structured output enables machine-readable results for downstream consumption, but the system already functions with free-form text. This is an enhancement, not a blocker.

**Independent Test**: Can be tested by configuring an agent with an output schema, assigning it a task, and verifying the returned result is valid JSON matching the schema.

**Acceptance Scenarios**:

1. **Given** an agent has an output schema defined, **When** it processes a task, **Then** its response is valid JSON conforming to the schema.
2. **Given** an agent's LLM response does not conform to the schema, **When** the output is parsed, **Then** the system falls back to storing the raw text (no crash or data loss).
3. **Given** an agent has no output schema defined, **When** it processes a task, **Then** it behaves identically to the current system (free-form text).
4. **Given** a downstream agent receives a structured result from an upstream task, **When** it processes its own task, **Then** it can reference specific fields from the upstream result.

---

### User Story 5 - Agent Requests Help from Another Agent Mid-Task (Priority: P3)

During task execution, an agent discovers it needs expertise from another agent. For example, the Xiaohongshu Specialist needs a cover image design specification from the UI Designer. The agent signals this need, the system dispatches a sub-task to the requested agent, and the result is returned to the original agent's context for it to continue working.

**Why this priority**: This enables emergent collaboration beyond what the CEO's initial task decomposition anticipates. However, it depends on the tool calling infrastructure (US1) and adds significant complexity. Best implemented after the core capabilities are stable.

**Independent Test**: Can be tested by configuring an agent with the "ask_agent" tool, triggering a task where the agent requests help, and verifying the helper agent's response is injected back into the original agent's context.

**Acceptance Scenarios**:

1. **Given** an agent has the ask_agent tool available, **When** it determines it needs another agent's expertise, **Then** it can invoke the ask_agent tool with a target agent and a specific request.
2. **Given** an ask_agent request is made, **When** the target agent processes the request, **Then** the result is returned to the requesting agent's message history and execution continues.
3. **Given** the target agent is busy or unavailable, **When** the ask_agent tool is invoked, **Then** the system queues the request and the requesting agent waits (with a configurable timeout).
4. **Given** an agent-to-agent request loop is detected (A asks B, B asks A), **When** the loop count exceeds 3, **Then** the system breaks the loop and returns an error to the requesting agent.

---

### Edge Cases

- What happens when a tool call hangs or takes too long? → Configurable per-tool timeout (default 30 seconds); on timeout, return error result to agent and let it decide how to proceed.
- What happens when an agent enters an infinite tool-calling loop? → Maximum tool call iterations per task (default 10); after limit, force the agent to return its current best output.
- What happens when dependency results are too large for the context window? → Truncate each dependency result to a configurable limit (default 4000 characters) with a truncation notice.
- What happens when structured output parsing fails repeatedly? → Fall back to raw text storage; log a warning; do not block task completion.
- What happens when an agent requests help from an agent that doesn't exist? → Return a clear error message to the requesting agent; it should continue with available information.
- What happens when self-review causes the agent to completely rewrite its output? → Accept the rewritten output; the observation view shows both draft and final for user review.
- What happens when multiple agents invoke the same tool simultaneously? → Tools should be stateless and safe for concurrent use; no serialization needed.

## Requirements *(mandatory)*

### Functional Requirements

**Tool Calling**
- **FR-001**: System MUST support defining available tools per agent role (configurable list of tool names).
- **FR-002**: Each tool MUST have a defined name, description, and parameter schema that the LLM can understand.
- **FR-003**: Agent execution MUST support an iterative loop: LLM responds → if tool call detected → execute tool → feed result back → continue until LLM provides final answer.
- **FR-004**: System MUST enforce a maximum number of tool call iterations per task execution to prevent infinite loops.
- **FR-005**: System MUST provide built-in tools: web_search (search engine query), web_fetch (fetch URL content), and create_artifact (save structured work product).
- **FR-006**: Tool call results and invocations MUST be visible in the real-time observation view.

**Context Quality**
- **FR-007**: When building agent context, the system MUST use human-readable agent names instead of UUIDs for message senders.
- **FR-008**: When executing a task with dependencies, the system MUST inject complete results from all prerequisite tasks into the agent's task description.
- **FR-009**: Dependency result injection MUST include the prerequisite task's title, the agent who completed it, and the result content.
- **FR-010**: Dependency results MUST be truncated to a configurable maximum per result to prevent context overflow.

**Multi-Step Reasoning**
- **FR-011**: System MUST support an optional self-review step where the agent evaluates its own output before submission.
- **FR-012**: Self-review MUST be configurable per agent role (enabled/disabled).
- **FR-013**: When self-review is enabled, the observation view MUST show both the initial draft and the final revised output.

**Structured Output**
- **FR-014**: Agent roles MUST support an optional output schema definition (JSON Schema format).
- **FR-015**: When an output schema is defined, the system MUST instruct the LLM to return JSON matching the schema.
- **FR-016**: System MUST attempt to parse the LLM response as JSON when a schema is defined, falling back to raw text on failure.
- **FR-017**: Parsed structured results MUST be stored separately from the raw text result for downstream consumption.

**Agent-to-Agent Collaboration**
- **FR-018**: System MUST support an ask_agent tool that allows one agent to request work from another agent during task execution.
- **FR-019**: Agent-to-agent requests MUST be tracked and visible in the observation view.
- **FR-020**: System MUST detect and break circular agent-to-agent request loops (threshold: 3 cycles).

**Backward Compatibility**
- **FR-021**: All new capabilities MUST be optional and disabled by default — existing agents without tools, schemas, or self-review MUST behave identically to the current system.
- **FR-022**: The LLM provider interface MUST remain backward compatible — new parameters (tools) MUST have safe defaults.

### Key Entities

- **Tool**: A callable capability available to agents. Has name, description, parameter schema, and an async execute function. Examples: web_search, web_fetch, create_artifact, ask_agent.
- **ToolCall**: A record of an agent invoking a tool during task execution. Has tool name, arguments, result, and timestamp. Part of the execution trace.
- **AgentRole** (extended): Gains optional fields: available_tools (list of tool names), output_schema (JSON Schema), enable_self_review (boolean).
- **Task** (extended): Gains optional field: result_structured (parsed JSON from structured output).

## Clarifications

### Session 2026-03-17

- Q: Should all agents have the same tools available? → A: No, tools should be configurable per agent role. Some agents (like UI Designer) may not need web_search, while Growth Hacker and AI Citation Strategist benefit most from it.
- Q: How should tool calling interact with the existing retry logic? → A: Retry logic applies to the overall agent execution (the full tool-calling loop), not individual LLM calls within the loop. If the entire loop fails after retries, the task is marked as failed.
- Q: Should the self-review use the same LLM or a different one? → A: Same LLM and same provider as the agent's primary configuration. The review is just an additional prompt turn, not a separate agent.
- Q: What is the maximum context size for dependency result injection? → A: Default 4000 characters per dependency result. Configurable in settings.
- Q: Should tools be provider-specific (Anthropic tool_use vs OpenAI function_calling)? → A: No, tools should be defined in a provider-agnostic format and each provider adapter translates to its native format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agents with tool access produce outputs that reference at least one piece of externally-sourced data when the task requires research, compared to zero with the current system.
- **SC-002**: Downstream agents that depend on upstream tasks have access to 100% of prerequisite task results (within the truncation limit), compared to the current probabilistic access through the 20-message context window.
- **SC-003**: Agent context messages display human-readable names for all senders, with zero UUID strings visible in the observation view.
- **SC-004**: Agents with self-review enabled produce outputs that pass a completeness check at a higher rate than single-shot outputs (measurable by CEO evaluation scores).
- **SC-005**: Agents with output schemas return parseable JSON at least 80% of the time (with graceful fallback for the remaining cases).
- **SC-006**: All new capabilities are backward compatible — existing agent configurations produce identical behavior with zero regressions.
- **SC-007**: Tool-calling loops complete within a configurable maximum iteration count, with zero infinite-loop incidents.
- **SC-008**: Agent-to-agent collaboration requests are resolved within 60 seconds (excluding the target agent's LLM processing time).
