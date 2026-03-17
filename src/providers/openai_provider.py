import openai

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": m.role, "content": m.content} for m in messages
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            if response.usage
            else None,
        )

    async def is_available(self) -> bool:
        return bool(settings.openai_api_key)
