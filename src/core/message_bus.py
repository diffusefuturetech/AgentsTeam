import asyncio
import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.message import Message, MessageType

logger = logging.getLogger(__name__)


class MessageBus:
    """Central message routing system for agent-to-agent communication.

    Handles message delivery, persistence, loop detection, and WebSocket broadcasting.
    """

    def __init__(self):
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._subscribers: list[asyncio.Queue] = []
        self._delegation_counts: dict[UUID, int] = {}  # task_id -> count
        self.max_delegations = 3

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to receive all messages (for WebSocket broadcast)."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber."""
        if q in self._subscribers:
            self._subscribers.remove(q)

    def set_role_names(self, role_names: dict[UUID, str]):
        """Set role ID to name mapping for readable logs."""
        self._role_names = role_names

    def resolve_name(self, role_id: UUID | None) -> str:
        """Resolve a role ID to a human-readable agent name."""
        if role_id is None:
            return "system"
        names = getattr(self, "_role_names", {})
        return names.get(role_id, str(role_id)[:8])

    def _resolve_name(self, role_id: UUID | None) -> str:
        return self.resolve_name(role_id)

    async def publish(
        self,
        session: AsyncSession,
        session_id: UUID,
        sender_role_id: UUID | None,
        receiver_role_id: UUID | None,
        message_type: MessageType,
        content: str,
        task_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> Message:
        """Publish a message: persist to DB, broadcast to subscribers, queue for processing."""
        message = Message(
            id=uuid4(),
            session_id=session_id,
            sender_role_id=sender_role_id,
            receiver_role_id=receiver_role_id,
            message_type=message_type,
            content=content,
            task_id=task_id,
            metadata_=metadata,
            created_at=datetime.utcnow(),
        )

        # Persist
        session.add(message)
        await session.commit()
        await session.refresh(message)

        # Broadcast to WebSocket subscribers
        for sub in self._subscribers:
            try:
                sub.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full, dropping message")

        # Queue for orchestrator processing
        await self._queue.put(message)

        sender = self._resolve_name(sender_role_id)
        receiver = self._resolve_name(receiver_role_id)
        logger.info(f"[{message_type.value}] {sender} → {receiver}")
        return message

    async def get_next_message(self) -> Message:
        """Get next message from the processing queue."""
        return await self._queue.get()

    def check_delegation_loop(self, task_id: UUID) -> bool:
        """Check if a task has been delegated too many times (loop detection).

        Returns True if loop detected (delegation count > max).
        """
        count = self._delegation_counts.get(task_id, 0) + 1
        self._delegation_counts[task_id] = count

        if count > self.max_delegations:
            logger.warning(f"Delegation loop detected for task {task_id} (count={count})")
            return True
        return False

    def reset_delegation_count(self, task_id: UUID):
        """Reset delegation count for a task (e.g., after escalation)."""
        self._delegation_counts.pop(task_id, None)

    async def get_history(
        self, session: AsyncSession, session_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        """Get message history for a session."""
        from sqlmodel import select

        result = await session.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())
