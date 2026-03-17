import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.models.agent import AgentRole
from src.models.team import TeamMember
from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry that manages agent instances from DB-stored role definitions."""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    async def load_team(self, session: AsyncSession, team_id) -> dict[str, BaseAgent]:
        """Load all agents for a team from DB."""
        self._agents.clear()

        # Get team members
        members = (await session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id)
        )).all()

        for member in members:
            role = await session.get(AgentRole, member.agent_role_id)
            if role and role.is_active:
                self._agents[role.role_key] = BaseAgent(role)
                logger.info(f"Loaded agent: {role.name} ({role.role_key})")

        return self._agents

    def get_agent(self, role_key: str) -> BaseAgent | None:
        return self._agents.get(role_key)

    def get_all_agents(self) -> dict[str, BaseAgent]:
        return self._agents

    def get_available_role_keys(self) -> list[str]:
        return list(self._agents.keys())

    def reload_agent(self, role: AgentRole):
        """Reload a single agent (after role update)."""
        if role.is_active:
            self._agents[role.role_key] = BaseAgent(role)
        elif role.role_key in self._agents:
            del self._agents[role.role_key]
