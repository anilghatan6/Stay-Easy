import uuid
from fastapi import WebSocket
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per property for real-time notification delivery."""

    def __init__(self):
        # {property_id: {user_id: WebSocket}}
        self.active_connections: dict[uuid.UUID, dict[uuid.UUID, WebSocket]] = {}

    async def connect(
        self, property_id: uuid.UUID, user_id: uuid.UUID, websocket: WebSocket
    ):
        await websocket.accept()
        if property_id not in self.active_connections:
            self.active_connections[property_id] = {}
        self.active_connections[property_id][user_id] = websocket
        logger.info(
            f"[NotificationDispatcher] User {user_id} connected to property {property_id}"
        )

    def disconnect(self, property_id: uuid.UUID, user_id: uuid.UUID):
        if property_id in self.active_connections:
            self.active_connections[property_id].pop(user_id, None)
            if not self.active_connections[property_id]:
                del self.active_connections[property_id]
        logger.info(
            f"[NotificationDispatcher] User {user_id} disconnected from property {property_id}"
        )

    async def broadcast_to_property(
        self, property_id: uuid.UUID, notification: dict
    ):
        conns = self.active_connections.get(property_id, {})
        disconnected = []
        for user_id, ws in conns.items():
            try:
                await ws.send_json(notification)
            except Exception:
                disconnected.append(user_id)
        for uid in disconnected:
            conns.pop(uid, None)
        if disconnected:
            logger.info(
                f"[NotificationDispatcher] Cleaned up {len(disconnected)} dead connections for property {property_id}"
            )

    def get_connected_users(self, property_id: uuid.UUID) -> set[uuid.UUID]:
        return set(self.active_connections.get(property_id, {}).keys())

    def is_connected(self, property_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return user_id in self.active_connections.get(property_id, {})


# Singleton instance
ws_manager = ConnectionManager()
