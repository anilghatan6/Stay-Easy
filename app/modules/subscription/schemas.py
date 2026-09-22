import uuid
from pydantic import BaseModel


class ResourceLimit(BaseModel):
    max: int
    used: int


class PropertyRoomUsage(BaseModel):
    property_id: uuid.UUID
    rooms: ResourceLimit


class SubscriptionUsageResponse(BaseModel):
    plan_name: str
    plan_slug: str
    status: str
    billing_cycle: str
    expires_at: str | None
    properties: ResourceLimit
    staff: ResourceLimit
    rooms_per_property: list[PropertyRoomUsage]
    bookings_this_month: ResourceLimit
    features: list[str]
