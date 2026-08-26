import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.modules.house_keeping.models.task_model import TaskType, TaskPriority


class WorkHistoryResponse(BaseModel):
    id: uuid.UUID
    activity_type: str
    room_name: Optional[str] = None
    room_floor: Optional[int] = None
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    maintenance_category: Optional[str] = None
    status: str
    assigned_by_name: Optional[str] = None
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkHistoryStatsResponse(BaseModel):
    total_tasks_completed: int
    total_maintenance_reports: int
    total_duration_minutes: int
    tasks_completed_today: int
    tasks_completed_this_week: int
    tasks_completed_this_month: int
