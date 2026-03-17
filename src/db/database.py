import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables and seed predefined data."""
    # Import all models so SQLModel registers them
    import src.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed predefined roles and default team
    async with async_session() as session:
        await seed_predefined_data(session)


async def seed_predefined_data(session: AsyncSession):
    """Seed predefined agent roles and default team if they don't exist."""
    from src.agents.predefined import PREDEFINED_ROLES
    from src.models.agent import AgentRole
    from src.models.team import Team, TeamMember

    # Check if already seeded
    existing = (await session.exec(select(AgentRole).where(AgentRole.is_predefined == True))).first()  # noqa: E712
    if existing:
        return

    logger.info("Seeding predefined agent roles and default team...")

    # Create predefined roles
    role_ids = {}
    for role_data in PREDEFINED_ROLES:
        role = AgentRole(id=uuid4(), **role_data)
        session.add(role)
        role_ids[role.role_key] = role.id

    # Create default team
    team = Team(id=uuid4(), name="Default Team", description="The default agent team with all predefined roles", is_default=True)
    session.add(team)

    # Add all predefined roles to default team
    for role_key, role_id in role_ids.items():
        member = TeamMember(id=uuid4(), team_id=team.id, agent_role_id=role_id)
        session.add(member)

    await session.commit()
    logger.info(f"Seeded {len(PREDEFINED_ROLES)} predefined roles and default team")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
