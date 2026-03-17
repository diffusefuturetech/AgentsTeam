import logging
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Schedules tasks respecting dependency order."""

    async def get_ready_tasks(self, session: AsyncSession, goal_id: UUID) -> list[Task]:
        """Get tasks that are ready to execute (pending + all dependencies completed)."""
        all_tasks = (await session.exec(
            select(Task).where(Task.goal_id == goal_id)
        )).all()

        completed_indices = set()
        task_list = list(all_tasks)

        # Build index map: task position -> task
        for i, task in enumerate(task_list):
            if task.status == TaskStatus.completed:
                completed_indices.add(i)

        ready = []
        for i, task in enumerate(task_list):
            if task.status != TaskStatus.pending:
                continue
            deps = task.depends_on or []
            if all(d in completed_indices for d in deps):
                ready.append(task)

        return ready

    async def get_all_tasks(self, session: AsyncSession, goal_id: UUID) -> list[Task]:
        """Get all tasks for a goal."""
        result = await session.exec(
            select(Task).where(Task.goal_id == goal_id).order_by(Task.created_at)
        )
        return list(result.all())

    async def get_task_results(self, session: AsyncSession, goal_id: UUID) -> list[dict]:
        """Get completed task results for evaluation."""
        tasks = await self.get_all_tasks(session, goal_id)
        return [
            {
                "title": t.title,
                "description": t.description,
                "assigned_to": str(t.assigned_to),
                "status": t.status.value,
                "result": t.result,
            }
            for t in tasks
        ]

    async def all_tasks_done(self, session: AsyncSession, goal_id: UUID) -> bool:
        """Check if all tasks for a goal are completed or failed."""
        tasks = await self.get_all_tasks(session, goal_id)
        if not tasks:
            return False
        return all(t.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.escalated) for t in tasks)
