"""Ask agent tool — allows one agent to request help from another agent mid-task."""

import logging

from src.tools.base import ToolDefinition

logger = logging.getLogger(__name__)

# Orchestrator reference will be set at startup
_orchestrator_ref = None


def set_orchestrator(orchestrator):
    """Set the orchestrator reference for agent-to-agent requests."""
    global _orchestrator_ref
    _orchestrator_ref = orchestrator


async def _handle_ask_agent(args: dict) -> str:
    """Dispatch a request to another agent and return their response."""
    target_role_key = args.get("target_role_key", "")
    request = args.get("request", "")

    if not target_role_key or not request:
        return "Error: 'target_role_key' and 'request' parameters are required."

    if _orchestrator_ref is None:
        return "Error: Orchestrator not available for agent-to-agent requests."

    try:
        result = await _orchestrator_ref.handle_agent_to_agent_request(
            target_role_key=target_role_key,
            request=request,
        )
        return result
    except Exception as e:
        logger.warning(f"ask_agent failed for '{target_role_key}': {e}")
        return f"Agent request failed: {e}"


ask_agent_tool = ToolDefinition(
    name="ask_agent",
    description="Request help from another agent on the team. Use this when you need expertise from a specific team member.",
    parameters={
        "type": "object",
        "properties": {
            "target_role_key": {
                "type": "string",
                "description": "The role_key of the agent to ask for help (e.g., 'ui_designer', 'content_creator')",
            },
            "request": {
                "type": "string",
                "description": "A clear, specific request describing what you need help with",
            },
        },
        "required": ["target_role_key", "request"],
    },
    handler=_handle_ask_agent,
)
