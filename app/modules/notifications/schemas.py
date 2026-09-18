import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    priority: str
    title: str
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    meta: Optional[dict] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
    unread_count: int


class MarkReadResponse(BaseModel):
    message: str
    unread_count: int


class NotificationTypeEnum(BaseModel):
    value: str
    label: str
