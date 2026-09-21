import uuid
from datetime import datetime, UTC

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationRecipient,
    NotificationType,
    NotificationPriority,
)
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_dispatcher import ConnectionManager
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class NotificationService:
    def __init__(
        self,
        db,
        notification_repo: NotificationRepository,
        dispatcher: ConnectionManager,
    ):
        self.db = db
        self.notification_repo = notification_repo
        self.dispatcher = dispatcher

    async def create_notification(
        self,
        notification_type: NotificationType,
        property_id: uuid.UUID,
        organization_id: uuid.UUID,
        title: str,
        message: str,
        recipient_user_ids: list[uuid.UUID] | None = None,
        roles: list[str] | None = None,
        actor_user_id: uuid.UUID | None = None,
        actor_guest_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        priority: NotificationPriority = NotificationPriority.INFO,
        meta: dict | None = None,
    ) -> Notification | None:
        """Create a notification, fan out to recipients, and broadcast via WebSocket.

        Recipients are resolved in this order:
        1. If recipient_user_ids is provided, use those directly.
        2. If roles is provided, resolve users by property + role.
        3. If neither, skip (no notification created).
        """
        # Resolve recipients
        if recipient_user_ids is None:
            if roles:
                recipient_user_ids = await self.resolve_recipients_by_roles(
                    property_id=property_id, roles=roles
                )
            else:
                recipient_user_ids = []

        if not recipient_user_ids:
            logger.info(
                f"[NotificationService] No recipients for {notification_type.value}, skipping."
            )
            return None

        notification = Notification(
            id=uuid.uuid4(),
            organization_id=organization_id,
            property_id=property_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            actor_guest_id=actor_guest_id,
            meta=meta,
        )

        recipients = [
            NotificationRecipient(
                id=uuid.uuid4(),
                notification_id=notification.id,
                user_id=uid,
            )
            for uid in recipient_user_ids
        ]

        await self.notification_repo.create_notification(notification, recipients)

        # Broadcast via WebSocket
        payload = {
            "id": str(notification.id),
            "type": notification_type.value,
            "priority": priority.value,
            "title": title,
            "message": message,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "actor_guest_id": str(actor_guest_id) if actor_guest_id else None,
            "meta": meta,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else datetime.now(UTC).isoformat(),
        }
        await self.dispatcher.broadcast_to_property(property_id, payload)

        await self.db.commit()

        logger.info(
            f"[NotificationService] Created {notification_type.value} for property {property_id}, "
            f"{len(recipient_user_ids)} recipients"
        )
        return notification

    async def get_notifications(
        self,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        notif_type: str | None = None,
    ) -> dict:
        notifications, total = await self.notification_repo.get_notifications(
            user_id=user_id,
            property_id=property_id,
            skip=skip,
            limit=limit,
            unread_only=unread_only,
            notif_type=notif_type,
        )
        unread_count = await self.notification_repo.get_unread_count(
            user_id=user_id,
            property_id=property_id,
        )
        logger.info(
            f"total notification for user {user_id} for property {property_id}: {total}"
        )
        logger.info(
            f"unread notification for user {user_id} for property {property_id}: {unread_count}"
        )
        return {
            "notifications": notifications,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": skip + len(notifications) < total,
            "unread_count": unread_count,
        }

    async def get_unread_count(
        self, user_id: uuid.UUID, property_id: uuid.UUID
    ) -> int:
        return await self.notification_repo.get_unread_count(
            user_id=user_id,
            property_id=property_id,
        )

    async def mark_as_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        return await self.notification_repo.mark_as_read(
            notification_id=notification_id,
            user_id=user_id,
        )

    async def mark_all_as_read(
        self, user_id: uuid.UUID, property_id: uuid.UUID
    ) -> int:
        return await self.notification_repo.mark_all_as_read(
            user_id=user_id,
            property_id=property_id,
        )

    async def resolve_recipients_by_roles(
        self, property_id: uuid.UUID, roles: list[str]
    ) -> list[uuid.UUID]:
        return await self.notification_repo.get_recipient_user_ids_by_roles(
            property_id=property_id,
            roles=roles,
        )

    async def resolve_recipient_by_staff_id(
        self, staff_id: uuid.UUID
    ) -> uuid.UUID | None:
        return await self.notification_repo.get_user_id_by_staff_id(staff_id)
