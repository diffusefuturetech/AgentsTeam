from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class MessageType(str, Enum):
    task_delegation = "task_delegation"
    task_response = "task_response"
    clarification_request = "clarification_request"
    clarification_response = "clarification_response"
    status_update = "status_update"
    group_discussion = "group_discussion"
    system_event = "system_event"
    user_response = "user_response"


class Message(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="session.id")
    sender_role_id: Optional[UUID] = Field(default=None, foreign_key="agentrole.id")
    receiver_role_id: Optional[UUID] = Field(default=None, foreign_key="agentrole.id")
    message_type: MessageType
    content: str
    task_id: Optional[UUID] = Field(default=None, foreign_key="task.id")
    metadata_: Optional[Any] = Field(default=None, sa_column=Column("metadata", JSON, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
