import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middlewares.auth_middlewares import CurrentStaff
from app.modules.notifications.dependencies import get_notification_service
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    MarkReadResponse,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.staff_mgmt.repositories.staffs_repository import StaffRepository
from app.modules.staff_mgmt.models.staffs_model import StaffStatus
from app.modules.staff_mgmt.dependencies import get_staff_repository
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


async def _verify_property_access(
    staff_user,
    property_id: uuid.UUID,
    staff_repo: StaffRepository,
):
    """Verify the staff member has access to the property and is active."""
    if not staff_user.is_active:
        raise HTTPException(status_code=403, detail="Staff account is inactive")

    # Admin (tenant owner) can access any property
    if staff_user.role == "admin":
        return

    # Non-admin: check staff is assigned to the property
    staff_record = await staff_repo.get_by_user_id_and_property(
        staff_user.id, property_id
    )
    if not staff_record:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this property",
        )
    if staff_record.status != StaffStatus.ACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Staff member is not active at this property",
        )


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
    staff_repo: StaffRepository = Depends(get_staff_repository),
):
    await _verify_property_access(staff, property_id, staff_repo)
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
    staff_repo: StaffRepository = Depends(get_staff_repository),
):
    await _verify_property_access(staff, property_id, staff_repo)
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
    property_id: uuid.UUID = Query(...),
    notification_service: NotificationService = Depends(get_notification_service),
    staff_repo: StaffRepository = Depends(get_staff_repository),
):
    await _verify_property_access(staff, property_id, staff_repo)
    await notification_service.mark_as_read(
        notification_id=notification_id,
        user_id=staff.id,
    )
    unread_count = await notification_service.get_unread_count(
        user_id=staff.id,
        property_id=property_id,
    )
    return StandardResponse(
        data=MarkReadResponse(
            message="Notification marked as read",
            unread_count=unread_count,
        )
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
    staff_repo: StaffRepository = Depends(get_staff_repository),
):
    await _verify_property_access(staff, property_id, staff_repo)
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
