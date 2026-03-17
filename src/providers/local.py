import json
import logging
import re

import httpx

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.tools.base import ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class LocalProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "llama3"):
        super().__init__(model_name)
        self.base_url = settings.local_model_url
        self.client = httpx.AsyncClient(timeout=120.0)

    def _inject_tool_descriptions(self, messages: list[LLMMessage], tools: list[ToolDefinition]) -> list[LLMMessage]:
        """For local models without native tool support, inject tool descriptions into system prompt."""
        if not tools:
            return messages

        tool_desc = "You have the following tools available. To use a tool, respond with [TOOL_CALL: tool_name({\"arg\": \"value\"})].\n\n"
        for t in tools:
            params = ", ".join(f"{k}: {v.get('type', 'string')}" for k, v in t.parameters.get("properties", {}).items())
            tool_desc += f"- {t.name}({params}): {t.description}\n"
        tool_desc += "\nAfter receiving tool results, continue your response. When done, provide your final answer without tool calls.\n"

        result = []
        for m in messages:
            if m.role == "system":
                result.append(LLMMessage(role="system", content=m.content + "\n\n" + tool_desc))
            else:
                result.append(m)
        return result

    def _parse_text_tool_calls(self, content: str) -> list[ToolCall]:
        """Parse text-based tool calls from local model output."""
        pattern = r'\[TOOL_CALL:\s*(\w+)\((.*?)\)\]'
        calls = []
        for i, match in enumerate(re.finditer(pattern, content, re.DOTALL)):
            name = match.group(1)
            args_str = match.group(2).strip()
            try:
                arguments = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                arguments = {"raw": args_str}
            calls.append(ToolCall(id=f"local_{i}", name=name, arguments=arguments))
        return calls

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        effective_messages = self._inject_tool_descriptions(messages, tools) if tools else messages

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": m.role, "content": m.content} for m in effective_messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage")
        content = choice["message"]["content"]

        # Parse text-based tool calls if tools were provided
        tool_calls = self._parse_text_tool_calls(content) if tools else None
        if tool_calls:
            # Remove tool call markers from content
            clean_content = re.sub(r'\[TOOL_CALL:\s*\w+\(.*?\)\]', '', content, flags=re.DOTALL).strip()
        else:
            clean_content = content
            tool_calls = None

        return LLMResponse(
            content=clean_content,
            model=data.get("model", self.model_name),
            usage=usage,
            tool_calls=tool_calls,
            stop_reason=choice.get("finish_reason"),
        )

    async def is_available(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
