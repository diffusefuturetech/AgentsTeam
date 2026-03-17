import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.agents.registry import AgentRegistry
from src.core.message_bus import MessageBus
from src.core.scheduler import TaskScheduler
from src.core.state_manager import StateManager
from src.db.database import async_session
from src.models.agent import AgentRole
from src.models.goal import Goal, GoalStatus
from src.models.message import MessageType
from src.models.session import Session, SessionStatus
from src.models.task import Task, TaskStatus
from src.models.team import Team

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestration loop that drives agent collaboration."""

    def __init__(self):
        self.message_bus = MessageBus()
        self.scheduler = TaskScheduler()
        self.registry = AgentRegistry()
        self.state_manager = StateManager()
        self._running = False
        self._current_session_id: UUID | None = None
        self._current_goal_id: UUID | None = None
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the orchestrator background loop."""
        if self._running:
            return
        self._running = True

        # Check for recoverable session on startup
        async with async_session() as session:
            recoverable = await self.state_manager.find_recoverable_session(session)
            if recoverable:
                goal = await self.state_manager.recover_session(session, recoverable)
                if goal:
                    self._current_session_id = recoverable.id
                    self._current_goal_id = goal.id
                    await self.registry.load_team(session, recoverable.team_id)
                    logger.info(f"Recovered session for goal: {goal.description[:80]}")

        # Check API keys
        available_providers = await self.state_manager.validate_api_keys()
        if not available_providers:
            logger.warning("No LLM providers configured! Set API keys in .env")

        self._task = asyncio.create_task(self._main_loop())
        logger.info("Orchestrator started")

    async def stop(self):
        """Stop the orchestrator."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Orchestrator stopped")

    async def _main_loop(self):
        """Main loop: check for active/queued goals and process them."""
        while self._running:
            try:
                async with async_session() as session:
                    # Check for active goal
                    active_goal = (await session.exec(
                        select(Goal).where(Goal.status == GoalStatus.active)
                    )).first()

                    if active_goal:
                        await self._process_active_goal(session, active_goal)
                    else:
                        # Check for queued goals
                        next_goal = (await session.exec(
                            select(Goal)
                            .where(Goal.status == GoalStatus.queued)
                            .order_by(Goal.queue_position)
                        )).first()

                        if next_goal:
                            await self._activate_goal(session, next_goal)

                await asyncio.sleep(2)  # Poll interval

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in orchestrator main loop")
                await asyncio.sleep(5)

    async def _activate_goal(self, session: AsyncSession, goal: Goal):
        """Activate a queued goal: create session, load team, decompose via CEO."""
        logger.info(f"Activating goal: {goal.description[:100]}")

        # Get team
        team = await session.get(Team, goal.team_id)
        if not team:
            logger.error(f"Team {goal.team_id} not found for goal {goal.id}")
            return

        # Load agents for this team
        await self.registry.load_team(session, team.id)

        # Create session
        sess = Session(
            id=uuid4(),
            goal_id=goal.id,
            team_id=team.id,
            status=SessionStatus.running,
            started_at=datetime.utcnow(),
            last_checkpoint_at=datetime.utcnow(),
        )
        session.add(sess)

        # Update goal status
        goal.status = GoalStatus.active
        goal.session_id = sess.id
        goal.started_at = datetime.utcnow()
        session.add(goal)
        await session.commit()

        self._current_session_id = sess.id
        self._current_goal_id = goal.id

        # Publish system event
        await self.message_bus.publish(
            session=session,
            session_id=sess.id,
            sender_role_id=None,
            receiver_role_id=None,
            message_type=MessageType.system_event,
            content=f"Goal activated: {goal.description}",
        )

        # CEO decomposes the goal
        ceo = self.registry.get_agent("ceo")
        if not ceo:
            logger.error("No CEO agent found in team")
            return

        available_agents = [k for k in self.registry.get_available_role_keys() if k != "ceo"]

        await self.message_bus.publish(
            session=session,
            session_id=sess.id,
            sender_role_id=ceo.role.id,
            receiver_role_id=None,
            message_type=MessageType.status_update,
            content="Analyzing goal and creating task breakdown...",
        )

        tasks_data = await ceo.decompose_goal(goal.description, available_agents)

        # Create tasks in DB
        role_map = {}
        for agent in self.registry.get_all_agents().values():
            role_map[agent.role_key] = agent.role.id

        for i, td in enumerate(tasks_data):
            assigned_role_key = td.get("assigned_to", available_agents[0])
            assigned_role_id = role_map.get(assigned_role_key, role_map.get(available_agents[0]))

            # Convert depends_on indices to be stored as-is (indices within this task list)
            depends = td.get("depends_on", [])

            task = Task(
                id=uuid4(),
                goal_id=goal.id,
                title=td["title"],
                description=td.get("description", ""),
                assigned_to=assigned_role_id,
                status=TaskStatus.pending,
                depends_on=depends,
                created_at=datetime.utcnow(),
            )
            session.add(task)

            await self.message_bus.publish(
                session=session,
                session_id=sess.id,
                sender_role_id=ceo.role.id,
                receiver_role_id=assigned_role_id,
                message_type=MessageType.task_delegation,
                content=f"Task: {td['title']}\n\nDescription: {td.get('description', '')}",
                task_id=task.id,
            )

        await session.commit()
        logger.info(f"Goal decomposed into {len(tasks_data)} tasks")

    async def _process_active_goal(self, session: AsyncSession, goal: Goal):
        """Process an active goal: dispatch ready tasks, check completion."""
        # If goal has no session yet, it needs activation first
        if not goal.session_id:
            await self._activate_goal(session, goal)
            return

        if not self._current_session_id:
            self._current_session_id = goal.session_id
            self._current_goal_id = goal.id
            # Reload team
            await self.registry.load_team(session, goal.team_id)

        # Get ready tasks
        ready_tasks = await self.scheduler.get_ready_tasks(session, goal.id)

        for task in ready_tasks:
            # Mark in progress
            task.status = TaskStatus.in_progress
            session.add(task)
            await session.commit()

            # Find assigned agent
            role = await session.get(AgentRole, task.assigned_to)
            if not role:
                task.status = TaskStatus.failed
                task.result = "Agent role not found"
                session.add(task)
                await session.commit()
                continue

            agent = self.registry.get_agent(role.role_key)
            if not agent:
                task.status = TaskStatus.failed
                task.result = "Agent not loaded"
                session.add(task)
                await session.commit()
                continue

            # Get context (recent messages for this session)
            history = await self.message_bus.get_history(session, self._current_session_id, limit=20)
            context = [
                {
                    "sender": str(m.sender_role_id) if m.sender_role_id else "system",
                    "content": m.content,
                }
                for m in history
            ]

            # Execute task
            try:
                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=role.id,
                    receiver_role_id=None,
                    message_type=MessageType.status_update,
                    content=f"Working on: {task.title}",
                    task_id=task.id,
                )

                result = await agent.process_message(
                    goal=goal.description,
                    task_description=f"{task.title}\n\n{task.description}",
                    context=context,
                )

                task.status = TaskStatus.completed
                task.result = result
                task.completed_at = datetime.utcnow()
                session.add(task)

                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=role.id,
                    receiver_role_id=None,
                    message_type=MessageType.task_response,
                    content=result[:2000],  # Truncate for message
                    task_id=task.id,
                )

            except Exception as e:
                logger.exception(f"Task execution failed: {task.title}")
                task.status = TaskStatus.failed
                task.result = str(e)
                session.add(task)

                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=None,
                    receiver_role_id=None,
                    message_type=MessageType.system_event,
                    content=f"Task failed: {task.title} - {str(e)[:200]}",
                    task_id=task.id,
                )

            await session.commit()

        # Check if all tasks are done
        if await self.scheduler.all_tasks_done(session, goal.id):
            await self._evaluate_goal_completion(session, goal)

    async def _evaluate_goal_completion(self, session: AsyncSession, goal: Goal):
        """Have CEO evaluate if the goal is complete."""
        ceo = self.registry.get_agent("ceo")
        if not ceo:
            return

        task_results = await self.scheduler.get_task_results(session, goal.id)
        evaluation = await ceo.evaluate_completion(goal.description, task_results)

        if evaluation.get("complete", False):
            goal.status = GoalStatus.pending_confirmation
            session.add(goal)
            await session.commit()

            await self.message_bus.publish(
                session=session,
                session_id=self._current_session_id,
                sender_role_id=ceo.role.id,
                receiver_role_id=None,
                message_type=MessageType.status_update,
                content=f"Goal complete! Summary: {evaluation.get('summary', '')}\n\nPlease confirm or extend this goal.",
            )
        else:
            # Create follow-up tasks
            next_steps = evaluation.get("next_steps", [])
            if next_steps:
                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=ceo.role.id,
                    receiver_role_id=None,
                    message_type=MessageType.status_update,
                    content=f"More work needed. Next steps: {json.dumps(next_steps)}",
                )

    async def handle_goal_confirm(self, goal_id: UUID):
        """User confirms goal completion."""
        async with async_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal or goal.status != GoalStatus.pending_confirmation:
                return

            goal.status = GoalStatus.completed
            goal.completed_at = datetime.utcnow()
            session.add(goal)

            # End session
            if goal.session_id:
                sess = await session.get(Session, goal.session_id)
                if sess:
                    sess.status = SessionStatus.completed
                    sess.ended_at = datetime.utcnow()
                    session.add(sess)

            await session.commit()
            self._current_session_id = None
            self._current_goal_id = None

    async def handle_goal_extend(self, goal_id: UUID, instructions: str):
        """User extends the goal with additional instructions."""
        async with async_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal or goal.status != GoalStatus.pending_confirmation:
                return

            goal.status = GoalStatus.active
            goal.description = f"{goal.description}\n\nAdditional instructions: {instructions}"
            session.add(goal)
            await session.commit()

            # CEO will re-decompose on next loop iteration
            ceo = self.registry.get_agent("ceo")
            if ceo and self._current_session_id:
                available_agents = [k for k in self.registry.get_available_role_keys() if k != "ceo"]
                new_tasks = await ceo.decompose_goal(instructions, available_agents)

                role_map = {}
                for agent in self.registry.get_all_agents().values():
                    role_map[agent.role_key] = agent.role.id

                for td in new_tasks:
                    assigned_role_key = td.get("assigned_to", available_agents[0])
                    assigned_role_id = role_map.get(assigned_role_key)

                    task = Task(
                        id=uuid4(),
                        goal_id=goal.id,
                        title=td["title"],
                        description=td.get("description", ""),
                        assigned_to=assigned_role_id,
                        status=TaskStatus.pending,
                        depends_on=td.get("depends_on", []),
                        created_at=datetime.utcnow(),
                    )
                    session.add(task)

                await session.commit()

    async def handle_goal_pause(self, goal_id: UUID):
        """Pause a running goal."""
        async with async_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal or goal.status != GoalStatus.active:
                return
            goal.status = GoalStatus.paused
            session.add(goal)
            if goal.session_id:
                sess = await session.get(Session, goal.session_id)
                if sess:
                    sess.status = SessionStatus.paused
                    session.add(sess)
            await session.commit()

    async def handle_goal_resume(self, goal_id: UUID):
        """Resume a paused goal."""
        async with async_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal or goal.status != GoalStatus.paused:
                return
            goal.status = GoalStatus.active
            session.add(goal)
            if goal.session_id:
                sess = await session.get(Session, goal.session_id)
                if sess:
                    sess.status = SessionStatus.running
                    session.add(sess)
            await session.commit()

    async def handle_goal_stop(self, goal_id: UUID):
        """Stop a running goal."""
        async with async_session() as session:
            goal = await session.get(Goal, goal_id)
            if not goal or goal.status not in (GoalStatus.active, GoalStatus.paused):
                return
            goal.status = GoalStatus.stopped
            goal.completed_at = datetime.utcnow()
            session.add(goal)
            if goal.session_id:
                sess = await session.get(Session, goal.session_id)
                if sess:
                    sess.status = SessionStatus.stopped
                    sess.ended_at = datetime.utcnow()
                    session.add(sess)
            await session.commit()
            self._current_session_id = None
            self._current_goal_id = None

    async def handle_user_response(self, goal_id: UUID, message_id: UUID, response: str):
        """Handle user response to agent clarification question."""
        async with async_session() as session:
            if self._current_session_id:
                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=None,
                    receiver_role_id=None,
                    message_type=MessageType.user_response,
                    content=response,
                    metadata={"in_reply_to": str(message_id)},
                )


# Global orchestrator instance
orchestrator = Orchestrator()
