import uuid
from fastapi import APIRouter, Depends, Query, Request

from app.middlewares.auth_middlewares import CurrentSuperAdmin
from app.modules.superadmin.schemas.announcement_schemas import (
    CreateAnnouncementRequest,
    AnnouncementResponse,
    AnnouncementListResponse,
)
from app.modules.superadmin.services.announcement_service import AnnouncementService
from app.modules.superadmin.dependencies import get_announcement_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin - Announcements"])


@router.post(
    "/announcements",
    response_model=StandardResponse[AnnouncementResponse],
    summary="Create a platform announcement",
)
async def create_announcement(
    payload: CreateAnnouncementRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    announcement = await announcement_service.create_announcement(
        title=payload.title,
        message=payload.message,
        priority=payload.priority,
        target=payload.target,
        target_admin_ids=payload.target_admin_ids,
        send_email=payload.send_email,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=AnnouncementResponse.model_validate(announcement))


@router.get(
    "/announcements",
    response_model=StandardResponse[AnnouncementListResponse],
    summary="List all announcements",
)
async def list_announcements(
    staff: CurrentSuperAdmin,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    announcements, total = await announcement_service.list_announcements(skip, limit)
    return StandardResponse(
        data=AnnouncementListResponse(
            announcements=[AnnouncementResponse.model_validate(a) for a in announcements],
            total=total,
        )
    )


@router.delete(
    "/announcements/{announcement_id}",
    summary="Delete an announcement",
)
async def delete_announcement(
    announcement_id: uuid.UUID,
    request: Request,
    staff: CurrentSuperAdmin,
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    await announcement_service.delete_announcement(
        announcement_id=announcement_id,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data={"message": "Announcement deleted successfully"})
