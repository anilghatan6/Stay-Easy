import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.modules.house_keeping.models.task_model import TaskType, TaskPriority, TaskStatus
from app.modules.pms.models.rooms_model import RoomStatus


class MyTaskResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    room_status: Optional[RoomStatus] = None
    floor_number: Optional[int] = None
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    assigned_by_name: Optional[str] = None
    due_time: datetime
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskStatusUpdateRequest(BaseModel):
    status: TaskStatus

    class Config:
        json_schema_extra = {
            "example": {"status": "IN_PROGRESS"}
        }
