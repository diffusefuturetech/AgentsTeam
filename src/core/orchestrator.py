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

    MAX_NESTED_AGENT_CALLS = 3

    def __init__(self):
        self.message_bus = MessageBus()
        self.scheduler = TaskScheduler()
        self.registry = AgentRegistry()
        self.state_manager = StateManager()
        self._running = False
        self._current_session_id: UUID | None = None
        self._current_goal_id: UUID | None = None
        self._task: asyncio.Task | None = None
        self._agent_call_depth: int = 0

    def _sync_role_names(self):
        """Push agent role_id->name mapping to MessageBus for readable logs."""
        names = {a.role.id: a.role.name for a in self.registry.get_all_agents().values()}
        self.message_bus.set_role_names(names)

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
                    self._sync_role_names()
                    logger.info(f"Recovered session for goal: {goal.description[:80]}")

        # Check API keys
        available_providers = await self.state_manager.validate_api_keys()
        if not available_providers:
            logger.warning("No LLM providers configured! Set API keys in .env")

        # Wire up ask_agent tool with orchestrator reference
        from src.tools.ask_agent import set_orchestrator
        set_orchestrator(self)

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
        self._sync_role_names()

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

        # Always sync from goal to ensure session_id is available after reload
        session_id = goal.session_id
        if not self._current_session_id:
            self._current_session_id = session_id
            self._current_goal_id = goal.id
            # Reload team
            await self.registry.load_team(session, goal.team_id)
            self._sync_role_names()

        # Get ready tasks
        ready_tasks = await self.scheduler.get_ready_tasks(session, goal.id)

        if not ready_tasks:
            # Check if all tasks are done (no ready tasks could mean all finished)
            if await self.scheduler.all_tasks_done(session, goal.id):
                await self._evaluate_goal_completion(session, goal)
            return

        # Mark all ready tasks as in_progress
        for task in ready_tasks:
            task.status = TaskStatus.in_progress
            session.add(task)
        await session.commit()

        # Execute all ready tasks in parallel (each with its own DB session)
        await asyncio.gather(
            *(self._execute_task(task.id, goal.id, goal.description, session_id) for task in ready_tasks)
        )

        # Check if all tasks are done
        async with async_session() as check_session:
            if await self.scheduler.all_tasks_done(check_session, goal.id):
                await self._evaluate_goal_completion(check_session, goal)

    async def _execute_task(
        self, task_id: UUID, goal_id: UUID, goal_description: str, session_id: UUID
    ):
        """Execute a single task with its own DB session (safe for parallel use)."""
        async with async_session() as session:
            task = await session.get(Task, task_id)
            if not task:
                return

            # Find assigned agent
            role = await session.get(AgentRole, task.assigned_to)
            if not role:
                task.status = TaskStatus.failed
                task.result = "Agent role not found"
                session.add(task)
                await session.commit()
                return

            agent = self.registry.get_agent(role.role_key)
            if not agent:
                task.status = TaskStatus.failed
                task.result = "Agent not loaded"
                session.add(task)
                await session.commit()
                return

            # Get context (recent messages for this session) — T005: use agent names
            history = await self.message_bus.get_history(session, session_id, limit=20)
            context = [
                {
                    "sender": self.message_bus.resolve_name(m.sender_role_id),
                    "content": m.content,
                }
                for m in history
            ]

            # T007: Inject dependency results into task description
            task_desc = f"{task.title}\n\n{task.description}"
            dep_results = await self.scheduler.get_dependency_results(
                session, goal_id, task,
                role_name_resolver=self.message_bus.resolve_name,
            )
            if dep_results:
                task_desc += "\n" + dep_results

            try:
                await self.message_bus.publish(
                    session=session,
                    session_id=session_id,
                    sender_role_id=role.id,
                    receiver_role_id=None,
                    message_type=MessageType.status_update,
                    content=f"Working on: {task.title}",
                    task_id=task.id,
                )

                # T024: Callback to publish tool call events to observation feed
                async def _on_tool_call(tc, tr):
                    args_preview = json.dumps(tc.arguments, ensure_ascii=False)[:200]
                    status = "✓" if not tr.is_error else "✗"
                    await self.message_bus.publish(
                        session=session,
                        session_id=session_id,
                        sender_role_id=role.id,
                        receiver_role_id=None,
                        message_type=MessageType.status_update,
                        content=f"🔧 Tool: {tc.name}({args_preview}) → {status}",
                        task_id=task.id,
                        metadata={"tool_call": True, "tool_name": tc.name},
                    )

                # T029: Callback to publish self-review events
                async def _on_self_review(draft, final):
                    await self.message_bus.publish(
                        session=session,
                        session_id=session_id,
                        sender_role_id=role.id,
                        receiver_role_id=None,
                        message_type=MessageType.status_update,
                        content=f"📝 Self-review: draft ({len(draft)} chars) → final ({len(final)} chars)",
                        task_id=task.id,
                        metadata={"self_review": True},
                    )

                result = await agent.process_message(
                    goal=goal_description,
                    task_description=task_desc,
                    context=context,
                    on_tool_call=_on_tool_call,
                    on_self_review=_on_self_review,
                )

                task.status = TaskStatus.completed
                task.result = result
                task.completed_at = datetime.utcnow()

                # T035: Attempt to parse structured output
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict):
                        task.result_structured = parsed
                except (json.JSONDecodeError, ValueError):
                    pass

                session.add(task)

                # T010: Raise truncation limit from 2000 to 8000
                await self.message_bus.publish(
                    session=session,
                    session_id=session_id,
                    sender_role_id=role.id,
                    receiver_role_id=None,
                    message_type=MessageType.task_response,
                    content=result[:8000],
                    task_id=task.id,
                )

            except Exception as e:
                logger.exception(f"Task execution failed: {task.title}")
                await session.rollback()
                task.status = TaskStatus.failed
                task.result = str(e)
                session.add(task)

                try:
                    await self.message_bus.publish(
                        session=session,
                        session_id=session_id,
                        sender_role_id=None,
                        receiver_role_id=None,
                        message_type=MessageType.system_event,
                        content=f"Task failed: {task.title} - {str(e)[:200]}",
                        task_id=task.id,
                    )
                except Exception:
                    logger.exception("Failed to publish task failure message")

            await session.commit()

    async def _evaluate_goal_completion(self, session: AsyncSession, goal: Goal):
        """Have CEO evaluate if the goal is complete."""
        ceo = self.registry.get_agent("ceo")
        if not ceo:
            return

        task_results = await self.scheduler.get_task_results(
            session, goal.id, role_name_resolver=self.message_bus.resolve_name
        )
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


    async def handle_agent_to_agent_request(
        self, target_role_key: str, request: str
    ) -> str:
        """Handle an agent-to-agent request via the ask_agent tool."""
        if self._agent_call_depth >= self.MAX_NESTED_AGENT_CALLS:
            return f"Error: Maximum nested agent call depth ({self.MAX_NESTED_AGENT_CALLS}) reached. Cannot dispatch further requests."

        agent = self.registry.get_agent(target_role_key)
        if not agent:
            available = list(self.registry.get_all_agents().keys())
            return f"Error: Agent '{target_role_key}' not found. Available agents: {available}"

        # Publish observation event
        if self._current_session_id:
            async with async_session() as session:
                await self.message_bus.publish(
                    session=session,
                    session_id=self._current_session_id,
                    sender_role_id=None,
                    receiver_role_id=agent.role.id,
                    message_type=MessageType.status_update,
                    content=f"🤝 Agent-to-agent: requesting help from {agent.role.name}",
                    metadata={"agent_to_agent": True, "target": target_role_key},
                )

        self._agent_call_depth += 1
        try:
            goal_desc = ""
            if self._current_goal_id:
                async with async_session() as session:
                    goal = await session.get(Goal, self._current_goal_id)
                    if goal:
                        goal_desc = goal.description

            result = await agent.process_message(
                goal=goal_desc,
                task_description=request,
                context=[],
            )
            return result
        finally:
            self._agent_call_depth -= 1


# Global orchestrator instance
orchestrator = Orchestrator()
