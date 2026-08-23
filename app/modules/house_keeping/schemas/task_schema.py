# app/modules/tasks/schemas/task_schema.py

import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.modules.house_keeping.models.task_model import TaskType, TaskPriority, TaskStatus


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