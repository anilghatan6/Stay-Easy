import uuid
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.models.staff_schedule_model import StaffSchedule
from app.modules.housekeeping_mobile.models.shift_swap_model import ShiftSwapRequest, SwapStatus
from app.modules.housekeeping_mobile.models.leave_request_model import LeaveRequest, LeaveStatus
from app.modules.staff_mgmt.models.staffs_model import Staff, ShiftType
from app.modules.auth.models import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class ScheduleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_schedule_by_date(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, target_date: date
    ) -> Optional[StaffSchedule]:
        logger.info(f"[ScheduleRepository] Fetching schedule for staff {staff_id} on {target_date}")
        try:
            stmt = select(StaffSchedule).where(
                StaffSchedule.staff_id == staff_id,
                StaffSchedule.property_id == property_id,
                StaffSchedule.shift_date == target_date,
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch schedule: {e}")
            raise RepositoryException("Could not fetch schedule.") from e

    async def get_schedule_history(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[StaffSchedule], int]:
        logger.info(f"[ScheduleRepository] Fetching schedule history for staff {staff_id}")
        try:
            stmt = (
                select(StaffSchedule)
                .where(
                    StaffSchedule.staff_id == staff_id,
                    StaffSchedule.property_id == property_id,
                )
                .order_by(StaffSchedule.shift_date.desc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(StaffSchedule)
                .where(
                    StaffSchedule.staff_id == staff_id,
                    StaffSchedule.property_id == property_id,
                )
            )

            result = await self.db.execute(stmt)
            schedules = list(result.scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return schedules, total
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch schedule history: {e}")
            raise RepositoryException("Could not fetch schedule history.") from e

    async def get_weekly_schedule(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[StaffSchedule]:
        logger.info(f"[ScheduleRepository] Fetching weekly schedule for staff {staff_id}")
        try:
            stmt = (
                select(StaffSchedule)
                .where(
                    StaffSchedule.staff_id == staff_id,
                    StaffSchedule.property_id == property_id,
                    StaffSchedule.shift_date >= start_date,
                    StaffSchedule.shift_date <= end_date,
                )
                .order_by(StaffSchedule.shift_date.asc())
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch weekly schedule: {e}")
            raise RepositoryException("Could not fetch weekly schedule.") from e

    async def get_monthly_schedule(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, year: int, month: int
    ) -> list[StaffSchedule]:
        logger.info(f"[ScheduleRepository] Fetching monthly schedule for staff {staff_id}")
        try:
            stmt = (
                select(StaffSchedule)
                .where(
                    StaffSchedule.staff_id == staff_id,
                    StaffSchedule.property_id == property_id,
                    func.extract("year", StaffSchedule.shift_date) == year,
                    func.extract("month", StaffSchedule.shift_date) == month,
                )
                .order_by(StaffSchedule.shift_date.asc())
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch monthly schedule: {e}")
            raise RepositoryException("Could not fetch monthly schedule.") from e

    async def create_swap_request(self, data: dict) -> ShiftSwapRequest:
        logger.info("[ScheduleRepository] Creating shift swap request")
        try:
            swap = ShiftSwapRequest(id=uuid.uuid4(), **data)
            self.db.add(swap)
            await self.db.flush()
            await self.db.refresh(swap)
            return swap
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[ScheduleRepository] Failed to create swap request: {e}")
            raise RepositoryException("Could not create swap request.") from e

    async def get_swap_requests_for_staff(
        self, staff_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[ShiftSwapRequest], int]:
        logger.info(f"[ScheduleRepository] Fetching swap requests for staff {staff_id}")
        try:
            stmt = (
                select(ShiftSwapRequest)
                .options(
                    joinedload(ShiftSwapRequest.requester_staff),
                    joinedload(ShiftSwapRequest.target_staff),
                )
                .where(
                    (ShiftSwapRequest.requester_staff_id == staff_id)
                    | (ShiftSwapRequest.target_staff_id == staff_id)
                )
                .order_by(ShiftSwapRequest.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(ShiftSwapRequest)
                .where(
                    (ShiftSwapRequest.requester_staff_id == staff_id)
                    | (ShiftSwapRequest.target_staff_id == staff_id)
                )
            )

            result = await self.db.execute(stmt)
            swaps = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return swaps, total
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch swap requests: {e}")
            raise RepositoryException("Could not fetch swap requests.") from e

    async def cancel_swap_request(
        self, swap_id: uuid.UUID, staff_id: uuid.UUID
    ) -> Optional[ShiftSwapRequest]:
        logger.info(f"[ScheduleRepository] Cancelling swap request {swap_id}")
        try:
            stmt = select(ShiftSwapRequest).where(
                ShiftSwapRequest.id == swap_id,
                ShiftSwapRequest.requester_staff_id == staff_id,
                ShiftSwapRequest.status == SwapStatus.PENDING,
            )
            result = await self.db.execute(stmt)
            swap = result.scalar_one_or_none()
            if swap:
                swap.status = SwapStatus.REJECTED
            return swap
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[ScheduleRepository] Failed to cancel swap request: {e}")
            raise RepositoryException("Could not cancel swap request.") from e

    async def create_leave_request(self, data: dict) -> LeaveRequest:
        logger.info("[ScheduleRepository] Creating leave request")
        try:
            leave = LeaveRequest(id=uuid.uuid4(), **data)
            self.db.add(leave)
            await self.db.flush()
            await self.db.refresh(leave)
            return leave
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[ScheduleRepository] Failed to create leave request: {e}")
            raise RepositoryException("Could not create leave request.") from e

    async def get_leave_requests_for_staff(
        self, staff_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[LeaveRequest], int]:
        logger.info(f"[ScheduleRepository] Fetching leave requests for staff {staff_id}")
        try:
            stmt = (
                select(LeaveRequest)
                .options(joinedload(LeaveRequest.staff))
                .where(LeaveRequest.staff_id == staff_id)
                .order_by(LeaveRequest.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(LeaveRequest)
                .where(LeaveRequest.staff_id == staff_id)
            )

            result = await self.db.execute(stmt)
            leaves = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return leaves, total
        except SQLAlchemyError as e:
            logger.error(f"[ScheduleRepository] Failed to fetch leave requests: {e}")
            raise RepositoryException("Could not fetch leave requests.") from e

    async def cancel_leave_request(
        self, leave_id: uuid.UUID, staff_id: uuid.UUID
    ) -> Optional[LeaveRequest]:
        logger.info(f"[ScheduleRepository] Cancelling leave request {leave_id}")
        try:
            stmt = select(LeaveRequest).where(
                LeaveRequest.id == leave_id,
                LeaveRequest.staff_id == staff_id,
                LeaveRequest.status == LeaveStatus.PENDING,
            )
            result = await self.db.execute(stmt)
            leave = result.scalar_one_or_none()
            if leave:
                leave.status = LeaveStatus.REJECTED
            return leave
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[ScheduleRepository] Failed to cancel leave request: {e}")
            raise RepositoryException("Could not cancel leave request.") from e
