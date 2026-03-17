# Research: Agent Capability Upgrade

**Feature**: 003-agent-capability-upgrade | **Date**: 2026-03-17

## R1: Tool Calling Implementation Pattern

**Decision**: Provider-agnostic tool definition with per-provider translation in the adapter layer

**Rationale**: Both Anthropic and OpenAI support native tool/function calling, but with different formats. Defining tools in a provider-agnostic schema and translating in each provider adapter keeps BaseAgent clean and avoids provider lock-in. The tool execution loop lives in BaseAgent, not in the provider.

**Alternatives considered**:
- **Provider-native tool schemas only**: Simpler per-provider but forces agents to know which provider they use. Breaks provider abstraction.
- **LangChain tools**: Adds a heavy dependency for something we can implement in ~50 lines. Violates Simplicity principle.
- **Text-based tool parsing** (regex on LLM output): Fragile, unreliable. Native tool calling is supported by all target providers.

**Key design points**:
- Define `ToolDefinition` dataclass: name, description, parameters (JSON Schema)
- Define `ToolCall` dataclass: id, name, arguments (dict)
- Extend `LLMResponse` with optional `tool_calls: list[ToolCall]`
- Each provider translates `ToolDefinition` to native format in `chat()`
- `BaseAgent.process_message()` runs a loop: call LLM → if tool_calls → execute → feed back → repeat
- Loop cap: configurable `max_tool_iterations` (default 10) to prevent infinite loops

## R2: Built-in Tool Set

**Decision**: Start with 3 core tools: web_search, web_fetch, create_artifact

**Rationale**: These cover the most impactful use cases identified in the spec. web_search enables research-grounded outputs, web_fetch allows reading specific URLs, create_artifact enables structured work product storage. The ask_agent tool (US5) is deferred to a later phase.

**Alternatives considered**:
- **Many tools at once** (calculator, code_exec, file_write, etc.): Over-scoped for MVP. Add tools incrementally.
- **No built-in tools, let users define all tools**: Too much setup friction. Predefined tools with opt-in per agent is the right balance.
- **MCP (Model Context Protocol) integration**: Interesting but adds external dependency and complexity. Can be added later as a tool source.

**Key design points**:
- `web_search(query: str) -> str`: Uses httpx to call a search API (DuckDuckGo instant answer or SerpAPI). Returns top 5 results as formatted text.
- `web_fetch(url: str) -> str`: Fetches URL content via httpx, strips HTML to text, truncates to 8000 chars.
- `create_artifact(name: str, artifact_type: str, content: str) -> str`: Creates an Artifact record in DB, returns confirmation with artifact ID.
- Tools are registered in a `ToolRegistry` singleton. Agents reference tools by name in their `available_tools` config.

## R3: Context Quality — Dependency Result Injection

**Decision**: Fetch dependency results from DB and prepend to task description

**Rationale**: The current system uses a 20-message context window, which is insufficient to guarantee that upstream task results are available to downstream agents. Explicit injection into the task description is deterministic, provider-agnostic, and requires no changes to the LLM provider interface.

**Alternatives considered**:
- **Increase context window to 100 messages**: Wastes tokens on irrelevant messages, doesn't guarantee dependency results are included.
- **Store results in a shared document**: Adds complexity (new entity, retrieval logic). Task results are already in the DB.
- **Agent-side retrieval tool**: Interesting but makes context availability dependent on agent behavior. Injection is deterministic.

**Key design points**:
- New method `scheduler.get_dependency_results(session, goal_id, task)` returns `[{title, agent_name, result}]`
- In `orchestrator._execute_task()`, dependency results are appended to task_description with clear delimiters
- Each result truncated to 4000 chars (configurable via settings)
- UUID-to-name resolution via existing `message_bus.resolve_name()` (already implemented but unused in context building)

## R4: Multi-Step Reasoning (Self-Review)

**Decision**: Optional second LLM call for self-review, configured per agent role

**Rationale**: A two-pass approach (generate → review → finalize) significantly improves output quality for complex tasks. Making it optional per agent keeps costs down for simple tasks. Using the same LLM for review (not a separate model) avoids additional provider configuration.

**Alternatives considered**:
- **Separate reviewer agent**: More powerful but adds inter-agent complexity. A self-review within the same agent is simpler and faster.
- **Always-on review for all agents**: Too expensive. Some tasks (status updates, simple lookups) don't benefit from review.
- **Multiple review rounds**: Diminishing returns after 1 review pass. Keep it simple with a single review step.

**Key design points**:
- New field on AgentRole: `enable_self_review: bool = False`
- After initial `process_message()` response, if self-review enabled, append response as "assistant" message and add a review prompt
- Review prompt: "Review your response for completeness, accuracy, and actionability. If improvements needed, provide a revised version. If satisfied, confirm the response is final."
- Store both draft and final in task metadata for observation transparency

## R5: Structured Output

**Decision**: Optional JSON Schema on AgentRole, with prompt-based enforcement and graceful fallback

**Rationale**: Prompt-based JSON enforcement works reliably with modern LLMs (GPT-4+, Claude 3+). Provider-native structured output (OpenAI's `response_format`, Anthropic's tool-based JSON) varies by provider. Starting with prompt-based enforcement is portable; native enforcement can be added per-provider later.

**Alternatives considered**:
- **Provider-native JSON mode only**: Not all providers support it identically. OpenAI has `response_format: json_object`, Anthropic doesn't have a direct equivalent.
- **Pydantic model per agent**: Too rigid. JSON Schema is flexible enough and stored in the DB for dynamic configuration.
- **Post-processing with Pydantic validation**: Useful addition but the core mechanism should be prompt-based for reliability.

**Key design points**:
- New field on AgentRole: `output_schema: Optional[dict] = None` (JSON Schema)
- When set, BaseAgent appends format instruction to task description
- After LLM response, attempt `json.loads()`. If fails, store raw text (no crash).
- New field on Task: `result_structured: Optional[dict] = None` for parsed JSON
- Downstream agents receiving structured results get them in a parseable format

## R6: Tool Calling in Local/Ollama Provider

**Decision**: Graceful degradation — local providers without tool support fall back to text-based tool hints

**Rationale**: Not all Ollama models support function calling. For models that do (e.g., llama3.1+), we pass tools natively. For models that don't, we include tool descriptions in the system prompt and parse the response for tool invocations using a simple format. This keeps local models usable.

**Alternatives considered**:
- **Disable tools entirely for local models**: Too limiting. Some local models are quite capable.
- **Require function-calling-capable models**: Too restrictive. Users may want to use lightweight models for some agents.

**Key design points**:
- LocalProvider checks model capabilities (if available) or falls back to text-based mode
- Text-based mode: tool descriptions added to system prompt, response parsed for `[TOOL_CALL: name(args)]` pattern
- This is a best-effort approach; agents using local models should not rely on high tool-calling accuracy
