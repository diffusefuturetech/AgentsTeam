"""Tool system for agent capabilities.

Provides a registry of tools that agents can invoke during task execution.
"""

from src.tools.base import ToolDefinition, ToolCall, ToolResult


class ToolRegistry:
    """Singleton registry for all available tools."""

    _instance: "ToolRegistry | None" = None

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_builtins()
        return cls._instance

    def _register_builtins(self):
        """Register all built-in tools."""
        from src.tools.web_search import web_search_tool
        from src.tools.web_fetch import web_fetch_tool
        from src.tools.create_artifact import create_artifact_tool
        from src.tools.ask_agent import ask_agent_tool

        for tool in [web_search_tool, web_fetch_tool, create_artifact_tool, ask_agent_tool]:
            self.register(tool)

    def register(self, tool: ToolDefinition):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_tools(self, names: list[str]) -> list[ToolDefinition]:
        """Get multiple tools by name, skipping unknown names."""
        return [self._tools[n] for n in names if n in self._tools]

    def list_all(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())


__all__ = ["ToolDefinition", "ToolCall", "ToolResult", "ToolRegistry"]
