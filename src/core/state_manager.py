import logging
from datetime import datetime
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.models.goal import Goal, GoalStatus
from src.models.session import Session, SessionStatus
from src.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistence, checkpointing, and recovery of agent execution state."""

    async def save_checkpoint(self, db: AsyncSession, session_id: UUID):
        """Save a checkpoint for the current session."""
        sess = await db.get(Session, session_id)
        if sess:
            sess.last_checkpoint_at = datetime.utcnow()
            db.add(sess)
            await db.commit()

    async def find_recoverable_session(self, db: AsyncSession) -> Session | None:
        """Find an active or paused session that can be recovered after restart."""
        result = await db.exec(
            select(Session).where(
                Session.status.in_([SessionStatus.running, SessionStatus.paused])
            )
        )
        return result.first()

    async def recover_session(self, db: AsyncSession, session: Session) -> Goal | None:
        """Recover a session: reset in-progress tasks to pending so they can be retried."""
        logger.info(f"Recovering session {session.id}")

        goal = await db.get(Goal, session.goal_id)
        if not goal:
            logger.error(f"Goal {session.goal_id} not found for session recovery")
            return None

        # Reset in-progress tasks to pending (they were interrupted)
        tasks = (await db.exec(
            select(Task).where(
                Task.goal_id == goal.id,
                Task.status == TaskStatus.in_progress,
            )
        )).all()

        for task in tasks:
            task.status = TaskStatus.pending
            db.add(task)
            logger.info(f"Reset interrupted task: {task.title}")

        # Ensure goal and session are in active state
        if goal.status == GoalStatus.paused:
            # Keep paused — user explicitly paused
            pass
        else:
            goal.status = GoalStatus.active
            db.add(goal)
            session.status = SessionStatus.running
            db.add(session)

        await db.commit()
        logger.info(f"Session recovered. Goal: {goal.description[:80]}")
        return goal

    async def validate_api_keys(self) -> list[str]:
        """Check which LLM providers have valid API keys configured."""
        from src.config import settings

        available = []
        if settings.anthropic_api_key:
            available.append("anthropic")
        if settings.openai_api_key:
            available.append("openai")
        if settings.local_model_url:
            available.append("local")
        return available
