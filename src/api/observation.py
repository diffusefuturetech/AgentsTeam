import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.orchestrator import orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observation"])


@router.websocket("/ws/observe")
async def observe(websocket: WebSocket):
    """WebSocket endpoint for real-time observation of agent activity."""
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Subscribe to message bus
    queue = orchestrator.message_bus.subscribe()

    try:
        # Two concurrent tasks: send messages to client, receive from client
        send_task = asyncio.create_task(_send_messages(websocket, queue))
        receive_task = asyncio.create_task(_receive_messages(websocket))

        done, pending = await asyncio.wait(
            [send_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        orchestrator.message_bus.unsubscribe(queue)
        logger.info("WebSocket client cleaned up")


async def _send_messages(websocket: WebSocket, queue: asyncio.Queue):
    """Send message bus events to WebSocket client."""
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=30)
            data = {
                "type": message.message_type.value,
                "data": {
                    "id": str(message.id),
                    "sender_role_id": str(message.sender_role_id) if message.sender_role_id else None,
                    "receiver_role_id": str(message.receiver_role_id) if message.receiver_role_id else None,
                    "content": message.content,
                    "task_id": str(message.task_id) if message.task_id else None,
                    "timestamp": message.created_at.isoformat() if message.created_at else None,
                    "metadata": message.metadata_,
                },
            }
            await websocket.send_json(data)
        except asyncio.TimeoutError:
            # Send ping to keep connection alive
            try:
                await websocket.send_json({"type": "ping", "data": {}})
            except Exception:
                break
        except Exception:
            break


async def _receive_messages(websocket: WebSocket):
    """Receive messages from WebSocket client (user responses)."""
    while True:
        try:
            data = await websocket.receive_json()
            if data.get("type") == "user_response":
                msg_data = data.get("data", {})
                message_id = msg_data.get("message_id")
                response = msg_data.get("response", "")
                if message_id and orchestrator._current_goal_id:
                    await orchestrator.handle_user_response(
                        orchestrator._current_goal_id,
                        UUID(message_id),
                        response,
                    )
        except WebSocketDisconnect:
            break
        except Exception:
            logger.exception("Error processing WebSocket message")
            break
