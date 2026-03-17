import httpx

from src.config import settings
from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse


class LocalProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "llama3"):
        super().__init__(model_name)
        self.base_url = settings.local_model_url
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
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
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model_name),
            usage=usage,
        )

    async def is_available(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
