# app/modules/favorites/schemas.py

import uuid
from datetime import datetime
from pydantic import BaseModel


class FavoriteCreate(BaseModel):
    property_id: uuid.UUID


class FavoriteOut(BaseModel):
    property_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


