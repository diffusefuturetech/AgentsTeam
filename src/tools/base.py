"""Base types for the tool system."""

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolDefinition:
    """Defines a callable tool available to agents."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for input parameters
    handler: Callable[[dict], Awaitable[str]]  # async (args) -> result string


@dataclass
class ToolCall:
    """Represents a single tool invocation from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of executing a tool call."""

    call_id: str
    content: str
    is_error: bool = False
