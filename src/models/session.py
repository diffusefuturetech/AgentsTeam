from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class SessionStatus(str, Enum):
    running = "running"
    paused = "paused"
    stopped = "stopped"
    completed = "completed"


class Session(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    goal_id: UUID = Field(foreign_key="goal.id")
    team_id: UUID = Field(foreign_key="team.id")
    status: SessionStatus = Field(default=SessionStatus.running)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_checkpoint_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(default=None)
