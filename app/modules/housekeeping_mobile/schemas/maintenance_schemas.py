import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.modules.housekeeping_mobile.models.maintenance_report_model import MaintenanceCategory
from app.modules.house_keeping.models.task_model import TaskPriority, TaskStatus


class MaintenanceReportCreate(BaseModel):
    room_id: uuid.UUID
    category: MaintenanceCategory
    priority: TaskPriority = TaskPriority.MEDIUM
    description: str = Field(..., min_length=10, max_length=2000)


class MaintenanceReportResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    staff_name: str
    category: MaintenanceCategory
    priority: TaskPriority
    description: str
    photos: dict
    status: TaskStatus
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
