import uuid
import jwt
from jwt import PyJWTError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config.settings_config import settings
from app.modules.notifications.services.notification_dispatcher import ws_manager
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

router = APIRouter(tags=["Notifications WebSocket"])


@router.websocket("/notifications/ws/{property_id}")
async def notification_websocket(
    websocket: WebSocket,
    property_id: uuid.UUID,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time notifications.

    Connect with: ws://host/api/v1/notifications/ws/{property_id}?token={jwt}
    """
    # Authenticate
    user_id = None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            await websocket.close(code=4001, reason="Invalid token: missing sub")
            return
        user_id = uuid.UUID(user_id_str)
    except PyJWTError as e:
        logger.warning(f"[WebSocket] Auth failed: {e}")
        await websocket.close(code=4001, reason="Invalid token")
        return
    except ValueError:
        await websocket.close(code=4001, reason="Invalid user ID in token")
        return

    # Connect
    await ws_manager.connect(property_id=property_id, user_id=user_id, websocket=websocket)

    try:
        while True:
            # Keep connection alive; handle pings or client messages if needed
            data = await websocket.receive_text()
            # Client can send "ping" to keep alive
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(property_id=property_id, user_id=user_id)
    except Exception as e:
        logger.error(f"[WebSocket] Error for user {user_id}: {e}")
        ws_manager.disconnect(property_id=property_id, user_id=user_id)
