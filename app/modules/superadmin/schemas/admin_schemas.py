import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class CreateAdminRequest(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    password: str


class UpdateAdminRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    tenant_id: Optional[uuid.UUID] = None
    created_at: datetime


class AdminListResponse(BaseModel):
    admins: list[AdminResponse]
    total: int
    skip: int
    limit: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_email: str
    action: str
    target_type: str
    target_id: Optional[uuid.UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    skip: int
    limit: int


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    impersonated_admin_id: uuid.UUID
    impersonated_admin_email: str
