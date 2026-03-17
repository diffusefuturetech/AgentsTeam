from src.providers.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.providers.anthropic import AnthropicProvider
from src.providers.openai_provider import OpenAIProvider
from src.providers.local import LocalProvider

__all__ = [
    "BaseLLMProvider",
    "LLMMessage",
    "LLMResponse",
    "AnthropicProvider",
    "OpenAIProvider",
    "LocalProvider",
    "get_provider",
]

_provider_cache: dict[tuple[str, str], BaseLLMProvider] = {}


def get_provider(provider_name: str, model_name: str) -> BaseLLMProvider:
    key = (provider_name, model_name)
    if key not in _provider_cache:
        if provider_name == "anthropic":
            _provider_cache[key] = AnthropicProvider(model_name)
        elif provider_name == "openai":
            _provider_cache[key] = OpenAIProvider(model_name)
        elif provider_name == "local":
            _provider_cache[key] = LocalProvider(model_name)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    return _provider_cache[key]
