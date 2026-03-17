import json
import anthropic

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.tools.base import ToolCall, ToolDefinition


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "claude-sonnet-4-6"):
        super().__init__(model_name)
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert ToolDefinitions to Anthropic tool format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Convert LLMMessages to Anthropic message format (excluding system)."""
        result = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                })
            elif m.role == "assistant" and m.tool_calls:
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                result.append({"role": "assistant", "content": content})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        system_text = ""
        for m in messages:
            if m.role == "system":
                system_text = m.content
                break

        kwargs = dict(
            model=self.model_name,
            system=system_text,
            messages=self._convert_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        response = await self.client.messages.create(**kwargs)

        # Extract text content and tool calls
        text_content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return LLMResponse(
            content=text_content,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            tool_calls=tool_calls if tool_calls else None,
            stop_reason=response.stop_reason,
        )

    async def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)
