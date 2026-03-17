from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Artifact(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="task.id")
    name: str
    artifact_type: str
    content: str
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
