import anthropic

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "claude-sonnet-4-6"):
        super().__init__(model_name)
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system_text = ""
        for m in messages:
            if m.role == "system":
                system_text = m.content
                break

        non_system_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        response = await self.client.messages.create(
            model=self.model_name,
            system=system_text,
            messages=non_system_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)
