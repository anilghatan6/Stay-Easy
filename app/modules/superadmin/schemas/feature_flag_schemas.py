import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreateFeatureFlagRequest(BaseModel):
    name: str
    key: str
    description: Optional[str] = None
    is_enabled: bool = False


class UpdateFeatureFlagRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key: str
    description: Optional[str] = None
    is_enabled: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class FeatureFlagListResponse(BaseModel):
    flags: list[FeatureFlagResponse]
    total: int
