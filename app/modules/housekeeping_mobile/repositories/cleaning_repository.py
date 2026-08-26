import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.models.cleaning_submission_model import (
    CleaningSubmission,
    CleaningSubmissionStatus,
)
from app.modules.house_keeping.models.task_model import HousekeepingTask
from app.modules.pms.models.rooms_model import Rooms
from app.modules.staff_mgmt.models.staffs_model import Staff
from app.modules.auth.models import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class CleaningRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_submission(self, data: dict) -> CleaningSubmission:
        logger.info("[CleaningRepository] Creating cleaning submission")
        try:
            submission = CleaningSubmission(id=uuid.uuid4(), **data)
            self.db.add(submission)
            await self.db.flush()
            await self.db.refresh(submission)
            return submission
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[CleaningRepository] Failed to create submission: {e}")
            raise RepositoryException("Could not create cleaning submission.") from e

    async def get_submission_by_id(
        self, submission_id: uuid.UUID
    ) -> Optional[CleaningSubmission]:
        logger.info(f"[CleaningRepository] Fetching submission {submission_id}")
        try:
            stmt = (
                select(CleaningSubmission)
                .options(
                    joinedload(CleaningSubmission.task),
                    joinedload(CleaningSubmission.room),
                    joinedload(CleaningSubmission.staff),
                    joinedload(CleaningSubmission.reviewed_by),
                )
                .where(CleaningSubmission.id == submission_id)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[CleaningRepository] Failed to fetch submission: {e}")
            raise RepositoryException("Could not fetch submission.") from e

    async def get_submission_by_task_id(
        self, task_id: uuid.UUID
    ) -> Optional[CleaningSubmission]:
        logger.info(f"[CleaningRepository] Fetching submission by task {task_id}")
        try:
            stmt = (
                select(CleaningSubmission)
                .options(
                    joinedload(CleaningSubmission.task),
                    joinedload(CleaningSubmission.room),
                    joinedload(CleaningSubmission.staff),
                )
                .where(CleaningSubmission.task_id == task_id)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[CleaningRepository] Failed to fetch submission by task: {e}")
            raise RepositoryException("Could not fetch submission.") from e

    async def get_submissions_for_staff(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[CleaningSubmission], int]:
        logger.info(f"[CleaningRepository] Fetching submissions for staff {staff_id}")
        try:
            base_filter = (
                CleaningSubmission.staff_id == staff_id,
                CleaningSubmission.property_id == property_id,
            )

            stmt = (
                select(CleaningSubmission)
                .join(Rooms, CleaningSubmission.room_id == Rooms.id)
                .outerjoin(User, CleaningSubmission.reviewed_by_id == User.id)
                .where(*base_filter)
                .options(
                    joinedload(CleaningSubmission.task),
                    joinedload(CleaningSubmission.room),
                    joinedload(CleaningSubmission.staff),
                    joinedload(CleaningSubmission.reviewed_by),
                )
                .order_by(CleaningSubmission.submitted_at.desc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(CleaningSubmission)
                .where(*base_filter)
            )

            result = await self.db.execute(stmt)
            submissions = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return submissions, total
        except SQLAlchemyError as e:
            logger.error(f"[CleaningRepository] Failed to fetch submissions: {e}")
            raise RepositoryException("Could not fetch submissions.") from e

    async def get_pending_submissions_for_property(
        self, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[CleaningSubmission], int]:
        logger.info(
            f"[CleaningRepository] Fetching pending submissions for property {property_id}"
        )
        try:
            base_filter = (
                CleaningSubmission.property_id == property_id,
                CleaningSubmission.status == CleaningSubmissionStatus.PENDING_REVIEW,
            )

            stmt = (
                select(CleaningSubmission)
                .join(Rooms, CleaningSubmission.room_id == Rooms.id)
                .outerjoin(User, CleaningSubmission.reviewed_by_id == User.id)
                .where(*base_filter)
                .options(
                    joinedload(CleaningSubmission.task),
                    joinedload(CleaningSubmission.room),
                    joinedload(CleaningSubmission.staff),
                    joinedload(CleaningSubmission.reviewed_by),
                )
                .order_by(CleaningSubmission.submitted_at.asc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(CleaningSubmission)
                .where(*base_filter)
            )

            result = await self.db.execute(stmt)
            submissions = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return submissions, total
        except SQLAlchemyError as e:
            logger.error(
                f"[CleaningRepository] Failed to fetch pending submissions: {e}"
            )
            raise RepositoryException("Could not fetch pending submissions.") from e

    async def update_submission_status(
        self,
        submission_id: uuid.UUID,
        status: CleaningSubmissionStatus,
        reviewed_by_id: uuid.UUID,
        rejection_reason: Optional[str] = None,
    ) -> Optional[CleaningSubmission]:
        logger.info(
            f"[CleaningRepository] Updating submission {submission_id} to {status}"
        )
        try:
            submission = await self.get_submission_by_id(submission_id)
            if submission is None:
                return None
            submission.status = status
            submission.reviewed_by_id = reviewed_by_id
            from datetime import datetime, timezone

            submission.reviewed_at = datetime.now(timezone.utc)
            if rejection_reason:
                submission.rejection_reason = rejection_reason
            return submission
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[CleaningRepository] Failed to update submission: {e}")
            raise RepositoryException("Could not update submission.") from e
