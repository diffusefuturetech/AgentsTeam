from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.core.orchestrator import orchestrator
from src.db.database import get_session
from src.models.goal import Goal, GoalStatus
from src.models.team import Team
from src.models.task import Task

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreate(BaseModel):
    description: str
    team_id: UUID | None = None


class GoalExtend(BaseModel):
    instructions: str


class UserResponse(BaseModel):
    message_id: UUID
    response: str


@router.post("", status_code=201)
async def create_goal(data: GoalCreate, session: AsyncSession = Depends(get_session)):
    """Create a new goal and queue it."""
    # Get team (default if not specified)
    if data.team_id:
        team = await session.get(Team, data.team_id)
    else:
        team = (await session.exec(select(Team).where(Team.is_default == True))).first()  # noqa: E712

    if not team:
        raise HTTPException(status_code=404, detail="Team not found", headers=None)

    # Count queued goals for position
    queued = (await session.exec(select(Goal).where(Goal.status == GoalStatus.queued))).all()

    goal = Goal(
        id=uuid4(),
        description=data.description,
        status=GoalStatus.queued,
        team_id=team.id,
        queue_position=len(queued) + 1,
        created_at=datetime.utcnow(),
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)

    return {
        "id": str(goal.id),
        "description": goal.description,
        "status": goal.status.value,
        "queue_position": goal.queue_position,
        "created_at": goal.created_at.isoformat(),
    }


@router.get("")
async def list_goals(status: str | None = None, session: AsyncSession = Depends(get_session)):
    """List all goals with optional status filter."""
    query = select(Goal)
    if status:
        query = query.where(Goal.status == GoalStatus(status))
    goals = (await session.exec(query.order_by(Goal.created_at.desc()))).all()

    return {
        "goals": [
            {
                "id": str(g.id),
                "description": g.description,
                "status": g.status.value,
                "queue_position": g.queue_position,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "started_at": g.started_at.isoformat() if g.started_at else None,
                "completed_at": g.completed_at.isoformat() if g.completed_at else None,
            }
            for g in goals
        ]
    }


@router.get("/{goal_id}")
async def get_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get goal details with tasks and progress."""
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    tasks = (await session.exec(select(Task).where(Task.goal_id == goal_id))).all()

    from src.models.agent import AgentRole
    task_list = []
    for t in tasks:
        role = await session.get(AgentRole, t.assigned_to)
        task_list.append({
            "id": str(t.id),
            "title": t.title,
            "status": t.status.value,
            "assigned_to": role.role_key if role else "unknown",
            "result": t.result[:500] if t.result else None,
        })

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status.value == "completed")
    in_progress = sum(1 for t in tasks if t.status.value == "in_progress")
    pending = sum(1 for t in tasks if t.status.value == "pending")

    return {
        "id": str(goal.id),
        "description": goal.description,
        "status": goal.status.value,
        "tasks": task_list,
        "progress": {
            "total_tasks": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
        },
    }


async def _get_goal_or_404(goal_id: UUID, session: AsyncSession) -> Goal:
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.post("/{goal_id}/pause")
async def pause_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status != GoalStatus.active:
        raise HTTPException(status_code=409, detail=f"Cannot pause goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_goal_pause(goal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "paused"}


@router.post("/{goal_id}/resume")
async def resume_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status != GoalStatus.paused:
        raise HTTPException(status_code=409, detail=f"Cannot resume goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_goal_resume(goal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "active"}


@router.post("/{goal_id}/stop")
async def stop_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status in (GoalStatus.completed, GoalStatus.stopped):
        raise HTTPException(status_code=409, detail=f"Cannot stop goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_goal_stop(goal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "stopped"}


@router.post("/{goal_id}/confirm")
async def confirm_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status not in (GoalStatus.active, GoalStatus.paused):
        raise HTTPException(status_code=409, detail=f"Cannot confirm goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_goal_confirm(goal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "completed"}


@router.post("/{goal_id}/extend")
async def extend_goal(goal_id: UUID, data: GoalExtend, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status not in (GoalStatus.active, GoalStatus.paused):
        raise HTTPException(status_code=409, detail=f"Cannot extend goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_goal_extend(goal_id, data.instructions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "active"}


@router.post("/{goal_id}/respond")
async def respond_to_agent(goal_id: UUID, data: UserResponse, session: AsyncSession = Depends(get_session)):
    goal = await _get_goal_or_404(goal_id, session)
    if goal.status != GoalStatus.active:
        raise HTTPException(status_code=409, detail=f"Cannot respond to goal with status '{goal.status.value}'")
    try:
        await orchestrator.handle_user_response(goal_id, data.message_id, data.response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "response_delivered"}
