import uuid
from datetime import datetime, UTC
from typing import Sequence

from sqlalchemy import select, func, update, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationRecipient,
    NotificationType,
)
from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.modules.pms.models.properties_model import Property
from app.modules.pms.models.tenants_model import Tenant
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        notification: Notification,
        recipients: list[NotificationRecipient],
    ) -> Notification:
        try:
            self.db.add(notification)
            for r in recipients:
                self.db.add(r)
            await self.db.flush()
            return notification
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to create notification: {e}")
            raise RepositoryException("Failed to create notification.")

    async def get_notifications(
        self,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        notif_type: str | None = None,
    ) -> tuple[list[dict], int]:
        try:
            # 1. Build the join condition
            join_cond = and_(
                NotificationRecipient.notification_id == Notification.id,
                NotificationRecipient.user_id == user_id
            )
            
            # 2. Build the dynamic where clauses
            base_where = [Notification.property_id == property_id]
            if notif_type:
                base_where.append(Notification.type == notif_type)
            if unread_only:
                base_where.append(NotificationRecipient.is_read == False)

            # 3. Create the window function for the total count
            # This counts matches across the entire filtered dataset before limit/offset apply
            total_count_col = func.count().over().label("total_count")

            # 4. Single Query: Fetch data columns AND the total count together
            stmt = (
                select(
                    Notification, 
                    NotificationRecipient.is_read, 
                    NotificationRecipient.read_at,
                    total_count_col
                )
                .join(NotificationRecipient, join_cond)
                .where(*base_where)
                .order_by(Notification.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            # 5. Process results
            notifications = []
            total = 0

            if rows:
                # Grab the total from the very first row (it will be identical across all rows)
                total = rows[0].total_count
                
                for notif, is_read, read_at, _ in rows:
                    notifications.append({
                        "id": notif.id,
                        "type": notif.type.value,
                        "priority": notif.priority.value,
                        "title": notif.title,
                        "message": notif.message,
                        "entity_type": notif.entity_type,
                        "entity_id": notif.entity_id,
                        "actor_user_id": notif.actor_user_id,
                        "actor_guest_id": notif.actor_guest_id,
                        "meta": notif.meta,
                        "is_read": is_read,
                        "read_at": read_at,
                        "created_at": notif.created_at,
                    })

            return notifications, total

        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to get notifications: {e}")
            raise RepositoryException("Failed to fetch notifications.")

    async def get_unread_count(
        self, user_id: uuid.UUID, property_id: uuid.UUID
    ) -> int:
        try:
            stmt = (
                select(func.count())
                .select_from(NotificationRecipient)
                .join(Notification, Notification.id == NotificationRecipient.notification_id)
                .where(
                    NotificationRecipient.user_id == user_id,
                    NotificationRecipient.is_read == False,
                    Notification.property_id == property_id,
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to get unread count: {e}")
            raise RepositoryException("Failed to fetch unread count.")

    async def mark_as_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        try:
            stmt = (
                update(NotificationRecipient)
                .where(
                    NotificationRecipient.notification_id == notification_id,
                    NotificationRecipient.user_id == user_id,
                    NotificationRecipient.is_read == False,
                )
                .values(is_read=True, read_at=datetime.now(UTC))
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to mark as read: {e}")
            raise RepositoryException("Failed to mark notification as read.")

    async def mark_all_as_read(
        self, user_id: uuid.UUID, property_id: uuid.UUID
    ) -> int:
        try:
            # Get all notification IDs for this property that are unread by this user
            notif_ids_subq = (
                select(Notification.id)
                .where(Notification.property_id == property_id)
            )

            stmt = (
                update(NotificationRecipient)
                .where(
                    NotificationRecipient.user_id == user_id,
                    NotificationRecipient.is_read == False,
                    NotificationRecipient.notification_id.in_(notif_ids_subq),
                )
                .values(is_read=True, read_at=datetime.now(UTC))
            )
            result = await self.db.execute(stmt)
            return result.rowcount
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to mark all as read: {e}")
            raise RepositoryException("Failed to mark notifications as read.")

    async def get_recipient_user_ids_by_roles(
        self, property_id: uuid.UUID, roles: list[str]
    ) -> list[uuid.UUID]:
        """Get user IDs for staff members assigned to a property with given roles.

        If 'admin' is in roles, also includes the tenant owner (property owner).
        """
        try:
            user_ids = set()

            # Always include the tenant owner (admin) if "admin" is in roles
            if "admin" in roles:
                admin_stmt = (
                    select(Tenant.owner_id)
                    .join(Property, Property.tenant_id == Tenant.id)
                    .where(Property.id == property_id)
                )
                result = await self.db.execute(admin_stmt)
                admin_id = result.scalar_one_or_none()
                if admin_id:
                    user_ids.add(admin_id)

            # Get staff users for the non-admin roles
            # Convert to uppercase to match JobRole enum values stored in DB
            staff_roles = [r.upper() for r in roles if r != "admin"]
            if staff_roles:
                staff_stmt = (
                    select(Staff.user_id)
                    .join(StaffProperty, StaffProperty.staff_id == Staff.id)
                    .where(
                        StaffProperty.property_id == property_id,
                        Staff.job_role.in_(staff_roles),
                        Staff.status == "ACTIVE",
                        Staff.user_id.isnot(None),
                    )
                )
                result = await self.db.execute(staff_stmt)
                for row in result.all():
                    user_ids.add(row[0])

            return list(user_ids)
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to get recipients by roles: {e}")
            raise RepositoryException("Failed to resolve notification recipients.")

    async def get_user_id_by_staff_id(self, staff_id: uuid.UUID) -> uuid.UUID | None:
        """Get User ID from a Staff record."""
        try:
            stmt = select(Staff.user_id).where(Staff.id == staff_id)
            result = await self.db.execute(stmt)
            row = result.scalar_one_or_none()
            return row
        except SQLAlchemyError as e:
            logger.error(f"[NotificationRepository] Failed to get user by staff_id: {e}")
            return None
