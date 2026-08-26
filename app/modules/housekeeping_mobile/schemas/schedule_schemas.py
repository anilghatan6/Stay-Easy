import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.modules.staff_mgmt.models.staffs_model import ShiftType
from app.modules.housekeeping_mobile.models.shift_swap_model import SwapStatus
from app.modules.housekeeping_mobile.models.leave_request_model import LeaveType, LeaveStatus


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    shift_date: date
    shift_type: ShiftType
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    tasks_assigned_today: int = 0
    tasks_completed_today: int = 0

    model_config = ConfigDict(from_attributes=True)


class ShiftSwapRequestCreate(BaseModel):
    target_staff_id: uuid.UUID
    target_shift: ShiftType
    reason: str = Field(..., min_length=5, max_length=500)


class ShiftSwapResponse(BaseModel):
    id: uuid.UUID
    requester_staff_id: uuid.UUID
    requester_staff_name: str
    target_staff_id: uuid.UUID
    target_staff_name: str
    requester_shift: ShiftType
    target_shift: ShiftType
    reason: str
    status: SwapStatus
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=5, max_length=1000)

    @field_validator("end_date")
    @classmethod
    def end_date_must_be_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class LeaveRequestResponse(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str
    status: LeaveStatus
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
