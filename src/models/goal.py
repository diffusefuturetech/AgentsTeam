from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class GoalStatus(str, Enum):
    queued = "queued"
    active = "active"
    pending_confirmation = "pending_confirmation"
    completed = "completed"
    extended = "extended"
    paused = "paused"
    stopped = "stopped"


class Goal(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    description: str
    status: GoalStatus = Field(default=GoalStatus.queued)
    team_id: UUID = Field(foreign_key="team.id")
    session_id: Optional[UUID] = Field(default=None, foreign_key="session.id")
    queue_position: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
