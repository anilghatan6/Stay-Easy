from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.config.redis_config import get_redis_client
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.notifications.services.notification_dispatcher import (
    ConnectionManager,
    ws_manager,
)


def get_notification_repository(
    db: AsyncSession = Depends(get_db),
) -> NotificationRepository:
    return NotificationRepository(db)


def get_notification_dispatcher() -> ConnectionManager:
    return ws_manager


def get_notification_service(
    db: AsyncSession = Depends(get_db),
    notification_repo: NotificationRepository = Depends(get_notification_repository),
    dispatcher: ConnectionManager = Depends(get_notification_dispatcher),
) -> NotificationService:
    return NotificationService(
        db=db,
        notification_repo=notification_repo,
        dispatcher=dispatcher,
    )
