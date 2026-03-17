from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Team(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: str = Field(default="")
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TeamMember(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id")
    agent_role_id: UUID = Field(foreign_key="agentrole.id")
