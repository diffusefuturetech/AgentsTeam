import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None


class BaseLLMProvider(ABC):
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send messages to LLM and get response."""
        ...

    async def chat_with_retry(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> LLMResponse:
        """Chat with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                return await self.chat(messages, temperature, max_tokens)
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait}s..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    raise

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        ...
