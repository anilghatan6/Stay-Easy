import uuid
from typing import Optional, List

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.repositories.cleaning_repository import CleaningRepository
from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
from app.modules.housekeeping_mobile.models.cleaning_submission_model import (
    CleaningSubmission,
    CleaningSubmissionStatus,
)
from app.modules.house_keeping.models.task_model import TaskStatus
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.models.activity_log_model import PropertyActivityLog
from app.Images.image_services import ImageService
from app.utils.exceptions import ServiceException, RoomNotFoundException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class CleaningService:
    def __init__(
        self,
        db: AsyncSession,
        cleaning_repo: CleaningRepository,
        task_repo: MobileTaskRepository,
        room_repo: RoomRepository,
        image_service: ImageService,
    ):
        self.db = db
        self.cleaning_repo = cleaning_repo
        self.task_repo = task_repo
        self.room_repo = room_repo
        self.image_service = image_service

    async def _log_activity(
        self,
        property_id: uuid.UUID,
        staff_id: Optional[uuid.UUID],
        staff_name: str,
        activity_type: str,
        description: str,
        room_id: Optional[uuid.UUID] = None,
        extra_data: Optional[dict] = None,
    ) -> None:
        """Log a property activity for the activity feed."""
        self.db.add(
            PropertyActivityLog(
                property_id=property_id,
                staff_id=staff_id,
                staff_name=staff_name,
                activity_type=activity_type,
                description=description,
                room_id=room_id,
                extra_data=extra_data,
            )
        )

    async def _get_staff_name_by_user_id(self, user_id: uuid.UUID) -> str:
        """Resolve staff display name from user_id."""
        staff = await self.task_repo.get_staff_by_user_id(user_id)
        if staff:
            return staff.full_name
        return "Unknown Staff"

    def _to_response_dict(self, submission: CleaningSubmission) -> dict:
        return {
            "id": submission.id,
            "task_id": submission.task_id,
            "property_id": submission.property_id,
            "room_id": submission.room_id,
            "room_name": submission.room.room_name if submission.room else "",
            "staff_id": submission.staff_id,
            "staff_name": submission.staff.full_name if submission.staff else "",
            "task_type": submission.task.task_type if submission.task else None,
            "task_priority": submission.task.priority if submission.task else None,
            "checklist_items": submission.checklist_items,
            "before_images": submission.before_images,
            "after_images": submission.after_images,
            "suppliers_used": submission.suppliers_used,
            "status": submission.status,
            "rejection_reason": submission.rejection_reason,
            "reviewed_by_name": (
                submission.reviewed_by.full_name
                if submission.reviewed_by
                else None
            ),
            "reviewed_at": submission.reviewed_at,
            "submitted_at": submission.submitted_at,
            "created_at": submission.created_at,
            "updated_at": submission.updated_at,
        }

    async def _process_images(
        self,
        files: Optional[List[UploadFile]],
        folder_prefix: str,
    ) -> list[str]:
        if not files:
            return []
        from app.utils.imgae_utils import process_image
        import asyncio

        urls = []
        for file in files[:5]:
            if file.content_type and file.content_type.startswith("image/"):
                raw_bytes = await file.read()
                optimized = await asyncio.to_thread(process_image, raw_bytes)
                url = await self.image_service.provider.save_image(
                    folder_name=folder_prefix,
                    image_bytes=optimized,
                )
                urls.append(url)
        return urls

    async def submit_for_inspection(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        task_id: uuid.UUID,
        checklist_items: list,
        suppliers_used: list,
        before_files: Optional[List[UploadFile]] = None,
        after_files: Optional[List[UploadFile]] = None,
    ) -> dict:
        # Verify task exists and is assigned to staff
        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)
        if task.assigned_staff_id != staff_id:
            raise ServiceException(
                user_message="Task not assigned to you", status_code=403
            )
        if task.property_id != property_id:
            raise ServiceException(
                user_message="Task not found for this property", status_code=404
            )

        # Verify task status allows submission
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS):
            raise ServiceException(
                user_message=f"Cannot submit cleaning for task with status {task.status}",
                status_code=400,
            )

        # Check if task already has a pending submission
        existing = await self.cleaning_repo.get_submission_by_task_id(task_id)
        if existing and existing.status == CleaningSubmissionStatus.PENDING_REVIEW:
            raise ServiceException(
                user_message="This task already has a pending submission",
                status_code=400,
            )

        # Verify room belongs to property
        try:
            await self.room_repo.get_room(task.room_id)
        except Exception:
            raise RoomNotFoundException("Room not found")

        # Process before and after images
        before_urls = await self._process_images(
            before_files,
            f"cleaning/{property_id}/{task.room_id}/before",
        )
        after_urls = await self._process_images(
            after_files,
            f"cleaning/{property_id}/{task.room_id}/after",
        )

        # Build suppliers list with quantities
        suppliers_list = [
            {"item": s.item.value, "quantity": s.quantity}
            for s in suppliers_used
        ]

        submission_data = {
            "task_id": task_id,
            "property_id": property_id,
            "room_id": task.room_id,
            "staff_id": staff_id,
            "checklist_items": {"items": [c.value for c in checklist_items]},
            "before_images": {"gallery": before_urls},
            "after_images": {"gallery": after_urls},
            "suppliers_used": {"suppliers": suppliers_list},
            "status": CleaningSubmissionStatus.PENDING_REVIEW,
        }

        submission = await self.cleaning_repo.create_submission(submission_data)

        # Transition task status to AWAITING_INSPECTION
        task.status = TaskStatus.AWAITING_INSPECTION

        # Log cleaning submission activity
        staff_name = await self._get_staff_name_by_user_id(staff_id)
        room_name = task.room.room_name if task.room else "Unknown"
        await self._log_activity(
            property_id=property_id,
            staff_id=staff_id,
            staff_name=staff_name,
            activity_type="CLEANING_SUBMITTED",
            description=f"Cleaning submitted for {room_name} - awaiting inspection",
            room_id=task.room_id,
            extra_data={
                "task_type": task.task_type,
                "room_name": room_name,
                "submitted_by": staff_name,
            },
        )

        await self.db.commit()
        await self.db.refresh(submission)
        return self._to_response_dict(submission)

    async def get_my_submissions(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        submissions, total = await self.cleaning_repo.get_submissions_for_staff(
            staff_id, property_id, skip, limit
        )
        return [self._to_response_dict(s) for s in submissions], total

    async def get_submission_detail(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, submission_id: uuid.UUID
    ) -> dict:
        submission = await self.cleaning_repo.get_submission_by_id(submission_id)
        if submission is None:
            raise ServiceException(
                user_message="Submission not found", status_code=404
            )
        if submission.staff_id != staff_id:
            raise ServiceException(
                user_message="Submission not found", status_code=404
            )
        if submission.property_id != property_id:
            raise ServiceException(
                user_message="Submission not found for this property", status_code=404
            )
        return self._to_response_dict(submission)

    async def list_pending_submissions(
        self, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        submissions, total = await self.cleaning_repo.get_pending_submissions_for_property(
            property_id, skip, limit
        )
        return [self._to_response_dict(s) for s in submissions], total

    async def review_submission(
        self,
        supervisor_user_id: uuid.UUID,
        property_id: uuid.UUID,
        submission_id: uuid.UUID,
        status: CleaningSubmissionStatus,
        rejection_reason: Optional[str] = None,
    ) -> dict:
        if status not in (
            CleaningSubmissionStatus.APPROVED,
            CleaningSubmissionStatus.REJECTED,
        ):
            raise ServiceException(
                user_message="Status must be APPROVED or REJECTED", status_code=400
            )

        if status == CleaningSubmissionStatus.REJECTED and not rejection_reason:
            raise ServiceException(
                user_message="Rejection reason is required",
                status_code=400,
            )

        submission = await self.cleaning_repo.get_submission_by_id(submission_id)
        if submission is None:
            raise ServiceException(
                user_message="Submission not found", status_code=404
            )
        if submission.property_id != property_id:
            raise ServiceException(
                user_message="Submission not found for this property", status_code=404
            )
        if submission.status != CleaningSubmissionStatus.PENDING_REVIEW:
            raise ServiceException(
                user_message="Submission has already been reviewed",
                status_code=400,
            )

        # Update submission status
        updated = await self.cleaning_repo.update_submission_status(
            submission_id, status, supervisor_user_id, rejection_reason
        )

        # Update task status based on review
        task = await self.task_repo.get_task_by_id(submission.task_id)
        if task:
            if status == CleaningSubmissionStatus.APPROVED:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.IN_PROGRESS

        # Log cleaning review activity
        supervisor_name = await self._get_staff_name_by_user_id(supervisor_user_id)
        room_name = submission.room.room_name if submission.room else "Unknown"
        staff_name = submission.staff.full_name if submission.staff else "Unknown"
        await self._log_activity(
            property_id=property_id,
            staff_id=supervisor_user_id,
            staff_name=supervisor_name,
            activity_type="CLEANING_REVIEWED",
            description=f"Cleaning {status.value.lower()} for {room_name} by {staff_name}",
            room_id=submission.room_id,
            extra_data={
                "review_status": status.value,
                "room_name": room_name,
                "cleaned_by": staff_name,
                "reviewed_by": supervisor_name,
                "rejection_reason": rejection_reason,
            },
        )

        await self.db.commit()
        await self.db.refresh(updated)
        return self._to_response_dict(updated)
