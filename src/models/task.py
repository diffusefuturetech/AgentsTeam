from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    escalated = "escalated"
    blocked = "blocked"


class Task(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    goal_id: UUID = Field(foreign_key="goal.id")
    title: str
    description: str = Field(default="")
    assigned_to: UUID = Field(foreign_key="agentrole.id")
    status: TaskStatus = Field(default=TaskStatus.pending)
    depends_on: Optional[List[str]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    delegation_count: int = Field(default=0)
    result: Optional[str] = Field(default=None)
    result_structured: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
