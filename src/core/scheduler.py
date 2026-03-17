import logging
from typing import Callable
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.config import settings
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

    async def get_dependency_results(
        self,
        session: AsyncSession,
        goal_id: UUID,
        task: Task,
        role_name_resolver: Callable[[UUID | None], str] | None = None,
    ) -> str:
        """Fetch results from dependency tasks and format them for injection into task description."""
        if not task.depends_on:
            return ""

        all_tasks = await self.get_all_tasks(session, goal_id)
        max_len = settings.max_dependency_result_length
        parts = []

        for dep_idx in task.depends_on:
            if not isinstance(dep_idx, int) or dep_idx >= len(all_tasks):
                continue
            dep_task = all_tasks[dep_idx]
            if dep_task.status != TaskStatus.completed or not dep_task.result:
                continue

            agent_name = (
                role_name_resolver(dep_task.assigned_to)
                if role_name_resolver
                else str(dep_task.assigned_to)
            )
            result_text = dep_task.result[:max_len]
            if len(dep_task.result) > max_len:
                result_text += "\n... (truncated)"

            parts.append(f"### {dep_task.title} (by {agent_name})\n{result_text}")

        if not parts:
            return ""

        return "\n\n--- 前置任务结果 ---\n" + "\n\n".join(parts) + "\n--- 结束 ---"

    async def get_task_results(
        self,
        session: AsyncSession,
        goal_id: UUID,
        role_name_resolver: Callable[[UUID | None], str] | None = None,
    ) -> list[dict]:
        """Get completed task results for evaluation."""
        tasks = await self.get_all_tasks(session, goal_id)
        return [
            {
                "title": t.title,
                "description": t.description,
                "assigned_to": role_name_resolver(t.assigned_to) if role_name_resolver else str(t.assigned_to),
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
