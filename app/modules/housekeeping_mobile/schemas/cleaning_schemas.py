import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.modules.housekeeping_mobile.models.cleaning_submission_model import (
    CleaningChecklistItem,
    SupplierItem,
    CleaningSubmissionStatus,
)
from app.modules.house_keeping.models.task_model import TaskType, TaskPriority


class SupplierUsage(BaseModel):
    item: SupplierItem
    quantity: int = Field(..., ge=1, le=999)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"item": "TOWELS", "quantity": 4}
        }
    )


class CleaningSubmissionCreateRequest(BaseModel):
    task_id: uuid.UUID
    checklist_items: List[CleaningChecklistItem] = Field(
        ..., min_length=1, max_length=12
    )
    suppliers_used: List[SupplierUsage] = Field(
        default_factory=list, max_length=20
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "checklist_items": [
                    "BED_MAKING",
                    "BATHROOM_CLEANING",
                    "FLOOR_MOPPING",
                ],
                "suppliers_used": [
                    {"item": "TOWELS", "quantity": 4},
                    {"item": "SHAMPOO", "quantity": 2},
                ],
            }
        }
    )


class CleaningSubmissionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    staff_id: uuid.UUID
    staff_name: str
    task_type: TaskType
    task_priority: TaskPriority
    checklist_items: dict
    before_images: dict
    after_images: dict
    suppliers_used: dict
    status: CleaningSubmissionStatus
    rejection_reason: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupervisorReviewRequest(BaseModel):
    status: CleaningSubmissionStatus = Field(
        ..., description="APPROVED or REJECTED"
    )
    rejection_reason: Optional[str] = Field(
        None, max_length=500, description="Required when rejecting"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "APPROVED",
                "rejection_reason": None,
            }
        }
    )
