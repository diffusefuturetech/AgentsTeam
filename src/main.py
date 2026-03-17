import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.agents import router as agents_router
from src.api.goals import router as goals_router
from src.api.history import router as history_router
from src.api.observation import router as observation_router
from src.config import settings
from src.core.orchestrator import orchestrator
from src.db.database import init_db

LOG_FORMAT = (
    '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}'
)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=LOG_FORMAT,
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Starting orchestrator...")
    await orchestrator.start()
    logger.info("AgentsTeam is ready!")
    yield
    logger.info("Shutting down orchestrator...")
    await orchestrator.stop()


app = FastAPI(
    title="AgentsTeam",
    description="Local multi-agent team system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(goals_router)
app.include_router(agents_router)
app.include_router(observation_router)
app.include_router(history_router)

# Serve static frontend files (must be last - catches all unmatched routes)
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_excludes=["*.db", "*.db-journal"],
    )
