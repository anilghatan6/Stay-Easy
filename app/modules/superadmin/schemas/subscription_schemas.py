import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ─── Subscription Plan Schemas ───

class CreatePlanRequest(BaseModel):
    name: str
    slug: str
    price_monthly: Decimal
    price_yearly: Optional[Decimal] = None
    max_properties: int = 1
    max_staff: int = 5
    max_rooms_per_property: int = 10
    max_bookings_per_month: int = 50
    features: Optional[dict] = None


class UpdatePlanRequest(BaseModel):
    name: Optional[str] = None
    price_monthly: Optional[Decimal] = None
    price_yearly: Optional[Decimal] = None
    max_properties: Optional[int] = None
    max_staff: Optional[int] = None
    max_rooms_per_property: Optional[int] = None
    max_bookings_per_month: Optional[int] = None
    features: Optional[dict] = None
    is_active: Optional[bool] = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    price_monthly: Decimal
    price_yearly: Optional[Decimal] = None
    max_properties: int
    max_staff: int
    max_rooms_per_property: int
    max_bookings_per_month: int
    features: Optional[dict] = None
    is_active: bool
    created_at: datetime


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]
    total: int


# ─── Tenant Subscription Schemas ───

class AssignSubscriptionRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str = "MONTHLY"


class UpgradeSubscriptionRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: Optional[str] = None


class TenantSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    billing_cycle: str
    starts_at: datetime
    expires_at: Optional[datetime] = None
    plan: Optional[PlanResponse] = None
