import uuid
from typing import Optional, List

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.repositories.maintenance_repository import MaintenanceRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.Images.image_services import ImageService
from app.utils.exceptions import ServiceException, RoomNotFoundException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class MaintenanceService:
    def __init__(
        self,
        db: AsyncSession,
        maintenance_repo: MaintenanceRepository,
        room_repo: RoomRepository,
        image_service: ImageService,
    ):
        self.db = db
        self.maintenance_repo = maintenance_repo
        self.room_repo = room_repo
        self.image_service = image_service

    def _to_response_dict(self, report) -> dict:
        return {
            "id": report.id,
            "property_id": report.property_id,
            "room_id": report.room_id,
            "room_name": report.room.room_name if report.room else "",
            "staff_name": report.staff.full_name if report.staff else "",
            "category": report.category,
            "priority": report.priority,
            "description": report.description,
            "photos": report.photos,
            "status": report.status,
            "resolved_at": report.resolved_at,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
        }

    async def create_report(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        room_id: uuid.UUID,
        category,
        priority,
        description: str,
        files: Optional[List[UploadFile]] = None,
    ) -> dict:
        # Verify room belongs to property
        try:
            await self.room_repo.get_room(room_id)
        except Exception:
            raise RoomNotFoundException("Room not found")

        # Process images
        photo_urls = []
        if files:
            for file in files[:5]:  # Max 5 images
                if file.content_type and file.content_type.startswith("image/"):
                    from app.utils.imgae_utils import process_image
                    import asyncio
                    raw_bytes = await file.read()
                    optimized = await asyncio.to_thread(process_image, raw_bytes)
                    url = await self.image_service.provider.save_image(
                        folder_name=f"maintenance/{property_id}",
                        image_bytes=optimized,
                    )
                    photo_urls.append(url)

        report_data = {
            "property_id": property_id,
            "room_id": room_id,
            "staff_id": staff_id,
            "category": category,
            "priority": priority,
            "description": description,
            "photos": {"gallery": photo_urls},
        }

        report = await self.maintenance_repo.create_report(report_data)
        await self.db.commit()
        await self.db.refresh(report)
        return self._to_response_dict(report)

    async def get_my_reports(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        reports, total = await self.maintenance_repo.get_reports_for_staff(
            staff_id, property_id, skip, limit
        )
        return [self._to_response_dict(r) for r in reports], total
