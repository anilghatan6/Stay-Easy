import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.repositories.schedule_repository import ScheduleRepository
from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
from app.modules.staff_mgmt.models.staffs_model import ShiftType
from app.utils.exceptions import ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class ScheduleService:
    def __init__(
        self,
        db: AsyncSession,
        schedule_repo: ScheduleRepository,
        task_repo: MobileTaskRepository,
    ):
        self.db = db
        self.schedule_repo = schedule_repo
        self.task_repo = task_repo

    async def get_today_schedule(self, staff_id: uuid.UUID, property_id: uuid.UUID) -> dict:
        today = date.today()
        schedule = await self.schedule_repo.get_schedule_by_date(staff_id, property_id, today)
        counts = await self.task_repo.get_task_counts_for_date(staff_id, property_id, today)

        if schedule is None:
            # Return default schedule from staff's shift
            staff = await self.task_repo.get_staff_by_user_id(staff_id)
            shift_type = staff.shift if staff else ShiftType.MORNING
            return {
                "id": None,
                "staff_id": staff_id,
                "shift_date": today,
                "shift_type": shift_type,
                "check_in_time": None,
                "check_out_time": None,
                **counts,
            }

        return {
            "id": schedule.id,
            "staff_id": schedule.staff_id,
            "shift_date": schedule.shift_date,
            "shift_type": schedule.shift_type,
            "check_in_time": schedule.check_in_time,
            "check_out_time": schedule.check_out_time,
            **counts,
        }

    async def get_schedule_history(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        schedules, total = await self.schedule_repo.get_schedule_history(
            staff_id, property_id, skip, limit
        )
        result = []
        for s in schedules:
            counts = await self.task_repo.get_task_counts_for_date(
                staff_id, property_id, s.shift_date
            )
            result.append({
                "id": s.id,
                "staff_id": s.staff_id,
                "shift_date": s.shift_date,
                "shift_type": s.shift_type,
                "check_in_time": s.check_in_time,
                "check_out_time": s.check_out_time,
                **counts,
            })
        return result, total

    async def get_weekly_schedule(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, start_date: Optional[date] = None
    ) -> list[dict]:
        if start_date is None:
            today = date.today()
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

        schedules = await self.schedule_repo.get_weekly_schedule(
            staff_id, property_id, start_date, end_date
        )
        result = []
        for s in schedules:
            counts = await self.task_repo.get_task_counts_for_date(
                staff_id, property_id, s.shift_date
            )
            result.append({
                "id": s.id,
                "staff_id": s.staff_id,
                "shift_date": s.shift_date,
                "shift_type": s.shift_type,
                "check_in_time": s.check_in_time,
                "check_out_time": s.check_out_time,
                **counts,
            })
        return result

    async def get_monthly_schedule(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, year: int, month: int
    ) -> list[dict]:
        schedules = await self.schedule_repo.get_monthly_schedule(
            staff_id, property_id, year, month
        )
        result = []
        for s in schedules:
            counts = await self.task_repo.get_task_counts_for_date(
                staff_id, property_id, s.shift_date
            )
            result.append({
                "id": s.id,
                "staff_id": s.staff_id,
                "shift_date": s.shift_date,
                "shift_type": s.shift_type,
                "check_in_time": s.check_in_time,
                "check_out_time": s.check_out_time,
                **counts,
            })
        return result

    async def get_leave_requests(
        self, staff_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        leaves, total = await self.schedule_repo.get_leave_requests_for_staff(
            staff_id, skip, limit
        )
        result = []
        for l in leaves:
            result.append({
                "id": l.id,
                "staff_id": l.staff_id,
                "staff_name": l.staff.full_name if l.staff else "Unknown",
                "leave_type": l.leave_type,
                "start_date": l.start_date,
                "end_date": l.end_date,
                "reason": l.reason,
                "status": l.status,
                "reviewed_at": l.reviewed_at,
                "created_at": l.created_at,
            })
        return result, total
