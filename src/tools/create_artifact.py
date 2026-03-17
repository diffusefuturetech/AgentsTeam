"""Create artifact tool — saves structured work products to the database."""

import logging
from datetime import datetime
from uuid import uuid4

from src.tools.base import ToolDefinition

logger = logging.getLogger(__name__)


async def _handle_create_artifact(args: dict) -> str:
    """Create an artifact record in the database."""
    title = args.get("title", "")
    content = args.get("content", "")
    artifact_type = args.get("artifact_type", "document")

    if not title or not content:
        return "Error: 'title' and 'content' parameters are required."

    try:
        from src.db.database import async_session
        from src.models.artifact import Artifact

        async with async_session() as session:
            artifact = Artifact(
                id=uuid4(),
                title=title,
                content=content,
                artifact_type=artifact_type,
                created_at=datetime.utcnow(),
            )
            session.add(artifact)
            await session.commit()

        return f"Artifact created: '{title}' (type: {artifact_type}, id: {artifact.id})"

    except ImportError:
        # Artifact model may not exist yet — store as plain text confirmation
        logger.warning("Artifact model not available, returning confirmation only")
        return f"Artifact noted: '{title}' (type: {artifact_type}). Note: Artifact model not yet implemented in database."
    except Exception as e:
        logger.warning(f"Create artifact failed: {e}")
        return f"Artifact creation failed: {e}"


create_artifact_tool = ToolDefinition(
    name="create_artifact",
    description="Create and save a structured work product (document, plan, report, etc.) to the database.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the artifact",
            },
            "content": {
                "type": "string",
                "description": "The full content of the artifact",
            },
            "artifact_type": {
                "type": "string",
                "description": "Type of artifact (e.g., 'document', 'plan', 'report', 'content')",
                "default": "document",
            },
        },
        "required": ["title", "content"],
    },
    handler=_handle_create_artifact,
)
