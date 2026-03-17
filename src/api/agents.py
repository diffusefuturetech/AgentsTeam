from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.db.database import get_session
from src.models.agent import AgentRole
from src.models.team import Team, TeamMember

router = APIRouter(tags=["agents"])


# --- Agent Role Endpoints ---


class AgentCreate(BaseModel):
    name: str
    role_key: str
    expertise: list[str]
    responsibilities: str
    system_prompt: str
    provider_name: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"


class AgentUpdate(BaseModel):
    name: str | None = None
    expertise: list[str] | None = None
    responsibilities: str | None = None
    system_prompt: str | None = None
    provider_name: str | None = None
    model_name: str | None = None


@router.get("/api/agents")
async def list_agents(
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """List all agent roles."""
    query = select(AgentRole)
    if not include_inactive:
        query = query.where(AgentRole.is_active == True)  # noqa: E712
    agents = (await session.exec(query.order_by(AgentRole.created_at))).all()

    return {
        "agents": [
            {
                "id": str(a.id),
                "name": a.name,
                "role_key": a.role_key,
                "expertise": a.expertise,
                "responsibilities": a.responsibilities,
                "system_prompt": a.system_prompt,
                "provider_name": a.provider_name,
                "model_name": a.model_name,
                "is_predefined": a.is_predefined,
                "is_active": a.is_active,
            }
            for a in agents
        ]
    }


@router.post("/api/agents", status_code=201)
async def create_agent(data: AgentCreate, session: AsyncSession = Depends(get_session)):
    """Create a custom agent role."""
    # Check uniqueness
    existing = (await session.exec(
        select(AgentRole).where(AgentRole.role_key == data.role_key)
    )).first()
    if existing:
        raise HTTPException(status_code=400, detail="role_key already exists")

    if not data.role_key.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="role_key must be lowercase alphanumeric + underscores")

    agent = AgentRole(
        id=uuid4(),
        name=data.name,
        role_key=data.role_key,
        expertise=data.expertise,
        responsibilities=data.responsibilities,
        system_prompt=data.system_prompt,
        provider_name=data.provider_name,
        model_name=data.model_name,
        is_predefined=False,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    return {
        "id": str(agent.id),
        "name": agent.name,
        "role_key": agent.role_key,
        "expertise": agent.expertise,
        "is_predefined": False,
    }


@router.put("/api/agents/{agent_id}")
async def update_agent(agent_id: UUID, data: AgentUpdate, session: AsyncSession = Depends(get_session)):
    """Update an agent role."""
    agent = await session.get(AgentRole, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.utcnow()

    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    return {
        "id": str(agent.id),
        "name": agent.name,
        "role_key": agent.role_key,
        "expertise": agent.expertise,
        "is_predefined": agent.is_predefined,
    }


@router.delete("/api/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, session: AsyncSession = Depends(get_session)):
    """Delete a custom agent role. Predefined roles are deactivated instead."""
    agent = await session.get(AgentRole, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.is_predefined:
        agent.is_active = False
        agent.updated_at = datetime.utcnow()
        session.add(agent)
    else:
        await session.delete(agent)

    await session.commit()


# --- Team Endpoints ---


class TeamCreate(BaseModel):
    name: str
    description: str = ""
    agent_role_ids: list[UUID]


class TeamMembersUpdate(BaseModel):
    agent_role_ids: list[UUID]


@router.get("/api/teams")
async def list_teams(session: AsyncSession = Depends(get_session)):
    """List all teams."""
    teams = (await session.exec(select(Team))).all()

    result = []
    for team in teams:
        members = (await session.exec(
            select(TeamMember).where(TeamMember.team_id == team.id)
        )).all()

        member_list = []
        for m in members:
            role = await session.get(AgentRole, m.agent_role_id)
            if role:
                member_list.append({"role_key": role.role_key, "name": role.name})

        result.append({
            "id": str(team.id),
            "name": team.name,
            "description": team.description,
            "is_default": team.is_default,
            "members": member_list,
        })

    return {"teams": result}


@router.post("/api/teams", status_code=201)
async def create_team(data: TeamCreate, session: AsyncSession = Depends(get_session)):
    """Create a new team."""
    # Validate: must include a CEO
    has_ceo = False
    for role_id in data.agent_role_ids:
        role = await session.get(AgentRole, role_id)
        if role and role.role_key == "ceo":
            has_ceo = True
            break
    if not has_ceo:
        raise HTTPException(status_code=400, detail="Team must include a CEO agent")

    team = Team(
        id=uuid4(),
        name=data.name,
        description=data.description,
        is_default=False,
        created_at=datetime.utcnow(),
    )
    session.add(team)

    for role_id in data.agent_role_ids:
        member = TeamMember(id=uuid4(), team_id=team.id, agent_role_id=role_id)
        session.add(member)

    await session.commit()
    await session.refresh(team)

    return {"id": str(team.id), "name": team.name}


@router.put("/api/teams/{team_id}/members")
async def update_team_members(
    team_id: UUID, data: TeamMembersUpdate, session: AsyncSession = Depends(get_session)
):
    """Update team membership."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Validate CEO
    has_ceo = False
    for role_id in data.agent_role_ids:
        role = await session.get(AgentRole, role_id)
        if role and role.role_key == "ceo":
            has_ceo = True
            break
    if not has_ceo:
        raise HTTPException(status_code=400, detail="Team must include a CEO agent")

    # Remove existing members
    existing = (await session.exec(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )).all()
    for m in existing:
        await session.delete(m)

    # Add new members
    for role_id in data.agent_role_ids:
        member = TeamMember(id=uuid4(), team_id=team_id, agent_role_id=role_id)
        session.add(member)

    await session.commit()

    # Return updated team
    members = (await session.exec(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )).all()
    member_list = []
    for m in members:
        role = await session.get(AgentRole, m.agent_role_id)
        if role:
            member_list.append({"role_key": role.role_key, "name": role.name})

    return {"id": str(team.id), "name": team.name, "members": member_list}
