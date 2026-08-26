import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.modules.house_keeping.models.task_model import TaskType, TaskPriority, TaskStatus
from app.modules.pms.models.rooms_model import RoomStatus


class CreateTaskRequest(BaseModel):
    room_id: uuid.UUID
    task_type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_staff_id: uuid.UUID
    due_time: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("due_time")
    @classmethod
    def due_time_must_be_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("due time must be a future timestamp")
        return v


class UpdateTaskRequest(BaseModel):
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    assigned_staff_id: Optional[uuid.UUID] = None
    due_time: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[TaskStatus] = None

    @field_validator("due_time")
    @classmethod
    def due_time_must_be_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("due time must be a future timestamp")
        return v


class TaskResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    assigned_staff_id: uuid.UUID
    assigned_staff_name: str
    due_time: datetime
    notes: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskTypeEnumResponse(BaseModel):
    value: str
    label: str


class BulkAssignTaskItem(BaseModel):
    task_type: TaskType
    room_id: uuid.UUID
    staff_id: uuid.UUID
    priority: TaskPriority = TaskPriority.MEDIUM
    notes: Optional[str] = Field(default=None, max_length=1000)
    due_time: datetime

    @field_validator("due_time")
    @classmethod
    def due_time_must_be_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("due time must be a future timestamp")
        return v


class BulkAssignRequest(BaseModel):
    tasks: List[BulkAssignTaskItem] = Field(..., min_length=1, max_length=50)


class BulkAssignResponse(BaseModel):
    created_count: int
    tasks: List[TaskResponse]


class TaskListResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    room_status: RoomStatus
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    assigned_staff_id: uuid.UUID
    assigned_staff_name: str
    assigned_by_id: Optional[uuid.UUID] = None
    assigned_by_name: Optional[str] = None
    due_time: datetime
    notes: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomStatusSummaryResponse(BaseModel):
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    dirty_rooms: int
    in_progress_rooms: int
    cleaning_rooms: int
    inspected_rooms: int
    blocked_rooms: int
    booked_rooms: int
    out_of_service_rooms: int
    maintenance_rooms: int


class StaffWorkSummaryResponse(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    total_assigned: int
    completed: int
    pending: int
    in_progress: int
    cancelled: int
