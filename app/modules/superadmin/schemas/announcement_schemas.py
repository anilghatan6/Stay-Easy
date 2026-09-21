import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreateAnnouncementRequest(BaseModel):
    title: str
    message: str
    priority: str = "INFO"
    target: str = "ALL"
    target_admin_ids: Optional[list[uuid.UUID]] = None
    send_email: bool = False


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    message: str
    priority: str
    target: str
    target_admin_ids: Optional[list] = None
    send_email: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime


class AnnouncementListResponse(BaseModel):
    announcements: list[AnnouncementResponse]
    total: int
