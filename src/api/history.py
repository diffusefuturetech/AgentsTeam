from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.db.database import get_session
from src.models.artifact import Artifact
from src.models.message import Message
from src.models.session import Session

router = APIRouter(prefix="/api/sessions", tags=["history"])


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    limit: int = 100,
    offset: int = 0,
    type: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """Get message history for a session."""
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    query = select(Message).where(Message.session_id == session_id)
    if type:
        from src.models.message import MessageType
        query = query.where(Message.message_type == MessageType(type))
    query = query.order_by(Message.created_at).offset(offset).limit(limit)

    messages = (await db.exec(query)).all()

    # Count total
    count_query = select(Message).where(Message.session_id == session_id)
    total = len((await db.exec(count_query)).all())

    return {
        "messages": [
            {
                "id": str(m.id),
                "sender_role_id": str(m.sender_role_id) if m.sender_role_id else None,
                "receiver_role_id": str(m.receiver_role_id) if m.receiver_role_id else None,
                "message_type": m.message_type.value,
                "content": m.content,
                "task_id": str(m.task_id) if m.task_id else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "total": total,
    }


@router.get("/{session_id}/artifacts")
async def get_artifacts(session_id: UUID, db: AsyncSession = Depends(get_session)):
    """Get artifacts produced during a session."""
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    from src.models.task import Task
    tasks = (await db.exec(select(Task).where(Task.goal_id == sess.goal_id))).all()
    task_ids = [t.id for t in tasks]

    if not task_ids:
        return {"artifacts": []}

    artifacts = []
    for tid in task_ids:
        arts = (await db.exec(select(Artifact).where(Artifact.task_id == tid))).all()
        artifacts.extend(arts)

    return {
        "artifacts": [
            {
                "id": str(a.id),
                "name": a.name,
                "artifact_type": a.artifact_type,
                "content": a.content,
                "task_id": str(a.task_id),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artifacts
        ]
    }
