from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    StringConstraints,

)
from typing import Annotated
import uuid
from datetime import datetime


class TenantBase(BaseModel):
       name: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        ..., 
        min_length=2, 
        max_length=255, 
        title="Tenant Name", 
        description="Name of the tenant"
    )
    
class TenantCreateSchema(TenantBase):
    pass

class TenantResponseSchema(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TenantUpdateSchema(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)] | None = Field(
        None, 
        title="Tenant Name", 
        description="Name of the tenant"
    )
