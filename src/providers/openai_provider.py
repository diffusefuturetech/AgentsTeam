import json
import openai

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.tools.base import ToolCall, ToolDefinition


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert ToolDefinitions to OpenAI function format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Convert LLMMessages to OpenAI message format."""
        result = []
        for m in messages:
            if m.role == "tool":
                result.append({
                    "role": "tool",
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                })
            elif m.role == "assistant" and m.tool_calls:
                msg = {"role": "assistant", "content": m.content or ""}
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
                result.append(msg)
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
        kwargs = dict(
            model=self.model_name,
            messages=self._convert_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        response = await self.client.chat.completions.create(**kwargs)

        choice = response.choices[0]

        # Parse tool calls from response
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments) if tc.function.arguments else {},
                )
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            if response.usage
            else None,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason,
        )

    async def is_available(self) -> bool:
        return bool(settings.openai_api_key)
