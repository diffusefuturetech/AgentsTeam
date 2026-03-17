import json
import logging
from typing import Awaitable, Callable
from src.config import settings
from src.models.agent import AgentRole
from src.providers import get_provider, LLMMessage
from src.tools import ToolRegistry, ToolDefinition, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents in the team."""

    def __init__(self, role: AgentRole):
        self.role = role
        self.provider = get_provider(role.provider_name, role.model_name)
        self._tools: list[ToolDefinition] | None = None

    def _get_tools(self) -> list[ToolDefinition] | None:
        """Resolve agent's available_tools to ToolDefinition list."""
        if self._tools is not None:
            return self._tools or None
        if not self.role.available_tools:
            self._tools = []
            return None
        registry = ToolRegistry.get_instance()
        self._tools = registry.get_tools(self.role.available_tools)
        return self._tools or None

    @property
    def role_key(self) -> str:
        return self.role.role_key

    @property
    def name(self) -> str:
        return self.role.name

    async def _execute_tool_call(self, call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        registry = ToolRegistry.get_instance()
        tool = registry.get(call.name)
        if not tool:
            return ToolResult(
                call_id=call.id,
                content=f"Unknown tool: {call.name}",
                is_error=True,
            )
        try:
            result = await tool.handler(call.arguments)
            return ToolResult(call_id=call.id, content=result)
        except Exception as e:
            logger.warning(f"Tool {call.name} failed: {e}")
            return ToolResult(call_id=call.id, content=f"Tool error: {e}", is_error=True)

    async def process_message(
        self,
        goal: str,
        task_description: str,
        context: list[dict],
        on_tool_call: "Callable[[ToolCall, ToolResult], Awaitable[None]] | None" = None,
        on_self_review: "Callable[[str, str], Awaitable[None]] | None" = None,
    ) -> str:
        """Process a task and return the result.

        Supports an iterative tool-calling loop: LLM responds → if tool_calls →
        execute tools → feed results back → repeat until no tool_calls or max iterations.

        Args:
            on_tool_call: Optional async callback invoked after each tool call with (call, result).
            on_self_review: Optional async callback invoked during self-review with (draft, final).
        """
        system_prompt = self.role.system_prompt.replace("{goal}", goal)

        messages = [LLMMessage(role="system", content=system_prompt)]

        # Add context messages
        for msg in context[-20:]:
            role = "assistant" if msg.get("sender") == self.role_key else "user"
            content = msg["content"]
            if msg.get("sender") and msg["sender"] != self.role_key:
                content = f"[From {msg['sender']}]: {content}"
            messages.append(LLMMessage(role=role, content=content))

        # Add current task (with optional structured output instruction)
        output_instruction = self._format_output_instruction()
        task_content = task_description
        if output_instruction:
            task_content += output_instruction
        messages.append(LLMMessage(role="user", content=task_content))

        tools = self._get_tools()
        max_iterations = settings.max_tool_iterations

        # Tool-calling loop
        for iteration in range(max_iterations):
            response = await self.provider.chat_with_retry(messages, tools=tools)

            if not response.tool_calls:
                content = response.content
                if self.role.enable_self_review:
                    logger.info(f"[{self.role.name}] Self-reviewing output...")
                    draft = content
                    content = await self._self_review(content, goal, task_description)
                    if on_self_review:
                        await on_self_review(draft, content)
                return content

            # Log tool calls
            for tc in response.tool_calls:
                logger.info(f"[{self.role.name}] Tool call: {tc.name}({json.dumps(tc.arguments, ensure_ascii=False)[:200]})")

            # Append assistant message with tool calls
            messages.append(LLMMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call and append results
            for tc in response.tool_calls:
                result = await self._execute_tool_call(tc)
                messages.append(LLMMessage(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.call_id,
                ))
                if on_tool_call:
                    await on_tool_call(tc, result)

        # Max iterations reached — do a final call without tools to get a response
        logger.warning(f"[{self.role.name}] Max tool iterations ({max_iterations}) reached, forcing final response")
        response = await self.provider.chat_with_retry(messages, tools=None)
        content = response.content
        if self.role.enable_self_review:
            logger.info(f"[{self.role.name}] Self-reviewing output...")
            draft = content
            content = await self._self_review(content, goal, task_description)
            if on_self_review:
                await on_self_review(draft, content)
        return content

    def _format_output_instruction(self) -> str | None:
        """Generate a prompt suffix requiring JSON output matching the schema."""
        if not self.role.output_schema:
            return None
        schema_str = json.dumps(self.role.output_schema, ensure_ascii=False, indent=2)
        return (
            f"\n\n--- 输出格式要求 ---\n"
            f"请以JSON格式返回你的结果，必须符合以下JSON Schema：\n"
            f"```json\n{schema_str}\n```\n"
            f"只输出JSON，不要包含其他文字或markdown标记。"
        )

    @staticmethod
    def _parse_structured_output(raw: str) -> dict | None:
        """Attempt to parse JSON from raw output, stripping markdown fences if needed."""
        text = raw.strip()
        if text.startswith("```"):
            # Strip ```json ... ``` fences
            lines = text.split("\n")
            if len(lines) >= 3:
                text = "\n".join(lines[1:])
                if text.rstrip().endswith("```"):
                    text = text.rstrip()[:-3].rstrip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    async def _self_review(self, draft: str, goal: str, task_description: str) -> str:
        """Perform a self-review step on the draft output."""
        review_prompt = (
            f"你刚刚完成了以下任务的初稿。请仔细审视你的输出，检查：\n"
            f"1. 完整性 — 是否覆盖了任务的所有要求？\n"
            f"2. 可执行性 — 建议是否具体、可操作？\n"
            f"3. 相关性 — 是否紧扣目标「{goal}」？\n"
            f"4. 质量 — 是否有错误、遗漏或可以改进的地方？\n\n"
            f"任务: {task_description[:500]}\n\n"
            f"你的初稿:\n{draft}\n\n"
            f"请直接输出改进后的最终版本。如果初稿已经足够好，可以原样输出。不要输出审查过程，只输出最终结果。"
        )

        system_prompt = self.role.system_prompt.replace("{goal}", goal)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="assistant", content=draft),
            LLMMessage(role="user", content=review_prompt),
        ]

        response = await self.provider.chat_with_retry(messages)
        return response.content

    async def decompose_goal(self, goal: str, available_agents: list[str]) -> list[dict]:
        """Decompose a goal into tasks (primarily used by CEO agent).

        Returns list of dicts: [{"title": "...", "description": "...", "assigned_to": "role_key", "depends_on": []}]
        """
        system_prompt = self.role.system_prompt.replace("{goal}", goal)

        prompt = f"""You are decomposing the following goal into actionable tasks for your team.

Goal: {goal}

Available team members (by role_key): {json.dumps(available_agents)}

Break this goal into 3-8 concrete, actionable tasks. Assign each task to the most appropriate team member.

Respond ONLY with a JSON array (no markdown, no explanation):
[
  {{"title": "Task title", "description": "Detailed description", "assigned_to": "role_key", "depends_on": []}}
]

Rules:
- Each task must be specific and actionable
- assigned_to must be one of the available role_keys
- depends_on is a list of task indices (0-based) that must complete before this task
- Order tasks logically
- Do not assign tasks to yourself (ceo) unless it's a review/decision task"""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self.provider.chat_with_retry(messages, temperature=0.3)

        # Parse JSON response
        try:
            text = response.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            tasks = json.loads(text)
            return tasks
        except (json.JSONDecodeError, IndexError):
            logger.error(f"Failed to parse goal decomposition: {response.content}")
            return [{"title": "Execute goal", "description": goal, "assigned_to": available_agents[0] if available_agents else "ceo", "depends_on": []}]

    async def evaluate_completion(self, goal: str, task_results: list[dict]) -> dict:
        """Evaluate if the goal is complete (used by CEO agent).

        Returns: {"complete": bool, "summary": "...", "next_steps": [...]}
        """
        results_text = "\n".join(
            f"- Task: {r['title']} (by {r['assigned_to']}): {r.get('result', 'No result')[:500]}"
            for r in task_results
        )

        prompt = f"""Evaluate if the following goal has been achieved based on the task results.

Goal: {goal}

Task Results:
{results_text}

Respond ONLY with JSON (no markdown):
{{"complete": true/false, "summary": "Brief summary of what was accomplished", "next_steps": ["step1", "step2"] }}

If complete is true, next_steps should be empty.
If complete is false, list what still needs to be done."""

        system_prompt = self.role.system_prompt.replace("{goal}", goal)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self.provider.chat_with_retry(messages, temperature=0.2)

        try:
            text = response.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {"complete": False, "summary": "Unable to evaluate", "next_steps": ["Review results manually"]}
