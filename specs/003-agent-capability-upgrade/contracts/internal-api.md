# Internal API Contracts: Agent Capability Upgrade

**Feature**: 003-agent-capability-upgrade | **Date**: 2026-03-17

This feature has no new external API endpoints. All changes are internal to the agent execution pipeline. This document defines the internal interfaces between components.

## Tool Definition Interface

### ToolDefinition Schema

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[[dict], Awaitable[str]]
```

### Built-in Tool Contracts

#### web_search

```json
{
  "name": "web_search",
  "description": "Search the web for current information. Returns top results with titles, URLs, and snippets.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search query"}
    },
    "required": ["query"]
  }
}
```

**Returns**: Formatted text with top 5 results (title, URL, snippet per result). Max 4000 chars.

#### web_fetch

```json
{
  "name": "web_fetch",
  "description": "Fetch and read the content of a web page. Returns the main text content.",
  "parameters": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "description": "URL to fetch"}
    },
    "required": ["url"]
  }
}
```

**Returns**: Extracted text content from the URL. Max 8000 chars. HTML tags stripped.

#### create_artifact

```json
{
  "name": "create_artifact",
  "description": "Save a work product (document, plan, specification, etc.) as a named artifact.",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "Artifact name"},
      "artifact_type": {"type": "string", "description": "Type: document, design, test_plan, code, report"},
      "content": {"type": "string", "description": "Full content of the artifact"}
    },
    "required": ["name", "artifact_type", "content"]
  }
}
```

**Returns**: Confirmation string with artifact ID.

## Provider Tool Translation

### OpenAI Format

```python
# ToolDefinition → OpenAI tools parameter
{
    "type": "function",
    "function": {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
    }
}
```

### Anthropic Format

```python
# ToolDefinition → Anthropic tools parameter
{
    "name": tool.name,
    "description": tool.description,
    "input_schema": tool.parameters,
}
```

### Response Parsing

**OpenAI**: `response.choices[0].message.tool_calls` → list of `{id, function: {name, arguments}}`
**Anthropic**: `response.content` blocks with `type="tool_use"` → `{id, name, input}`

## Dependency Result Injection Format

When a task has dependencies, the following is appended to `task_description`:

```
\n\n--- 前置任务结果 ---
\n### {task_title} (by {agent_name})
\n{result_content[:4000]}
\n
\n--- 前置任务结果结束 ---
```

## Self-Review Prompt

When `enable_self_review=True`, after the initial response, this prompt is appended:

```
请审查你刚才的回答，检查以下几点：
1. 完整性：是否覆盖了任务要求的所有方面？
2. 可执行性：建议是否具体、可操作？
3. 准确性：数据和引用是否正确？
4. 相关性：是否紧扣目标和任务描述？

如果需要改进，请提供修订版本。如果满意，请确认回答是最终版本。
```

## Observation View Changes

Tool calls and results are published as `status_update` messages to maintain WebSocket compatibility:

```json
{
  "type": "status_update",
  "data": {
    "sender_role_id": "agent-uuid",
    "content": "🔧 Calling tool: web_search(query='抖音 2026 算法趋势')",
    "task_id": "task-uuid",
    "metadata": {"tool_call": true, "tool_name": "web_search"}
  }
}
```
