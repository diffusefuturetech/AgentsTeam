from datetime import datetime
from uuid import UUID, uuid4
from typing import List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class AgentRole(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    role_key: str = Field(unique=True)
    expertise: List[str] = Field(sa_column=Column(JSON))
    responsibilities: str
    system_prompt: str
    provider_name: str = Field(default="anthropic")
    model_name: str = Field(default="claude-sonnet-4-6")
    is_predefined: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
