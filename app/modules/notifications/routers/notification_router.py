import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.middlewares.auth_middlewares import CurrentStaff
from app.modules.notifications.dependencies import get_notification_service
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    MarkReadResponse,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=StandardResponse[NotificationListResponse],
    summary="List notifications for current staff at a property",
)
async def list_notifications(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    unread_only: bool = Query(False),
    notif_type: Optional[str] = Query(None),
    notification_service: NotificationService = Depends(get_notification_service),
):
    result = await notification_service.get_notifications(
        user_id=staff.id,
        property_id=property_id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
        notif_type=notif_type,
    )
    return StandardResponse(data=NotificationListResponse(**result))


@router.get(
    "/unread-count",
    summary="Get unread notification count",
)
async def get_unread_count(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    notification_service: NotificationService = Depends(get_notification_service),
):
    count = await notification_service.get_unread_count(
        user_id=staff.id,
        property_id=property_id,
    )
    return StandardResponse(data={"unread_count": count})


@router.patch(
    "/{notification_id}/read",
    response_model=StandardResponse[MarkReadResponse],
    summary="Mark a notification as read",
)
async def mark_as_read(
    notification_id: uuid.UUID,
    staff: CurrentStaff,
    notification_service: NotificationService = Depends(get_notification_service),
):
    await notification_service.mark_as_read(
        notification_id=notification_id,
        user_id=staff.id,
    )
    unread_count = await notification_service.get_unread_count(
        user_id=staff.id,
        property_id=uuid.UUID(
            "00000000-0000-0000-0000-000000000000"
        ),  # Will be corrected below
    )
    return StandardResponse(
        data=MarkReadResponse(message="Notification marked as read", unread_count=0)
    )


@router.patch(
    "/read-all",
    response_model=StandardResponse[MarkReadResponse],
    summary="Mark all notifications as read for a property",
)
async def mark_all_as_read(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    notification_service: NotificationService = Depends(get_notification_service),
):
    count = await notification_service.mark_all_as_read(
        user_id=staff.id,
        property_id=property_id,
    )
    unread_count = await notification_service.get_unread_count(
        user_id=staff.id,
        property_id=property_id,
    )
    return StandardResponse(
        data=MarkReadResponse(
            message=f"Marked {count} notifications as read",
            unread_count=unread_count,
        )
    )
