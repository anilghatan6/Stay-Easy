import uuid
from fastapi import APIRouter, Depends

from app.middlewares.auth_middlewares import CurrentUser
from app.modules.subscription.enforcement_service import PlanEnforcementService
from app.modules.subscription.dependencies import get_plan_enforcement
from app.modules.subscription.schemas import SubscriptionUsageResponse, ResourceLimit, PropertyRoomUsage
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("/me", response_model=StandardResponse[SubscriptionUsageResponse])
async def get_my_subscription(
    current_user: CurrentUser,
    enforcement: PlanEnforcementService = Depends(get_plan_enforcement),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    usage = await enforcement.get_usage_summary(tenant_id)
    sub = await enforcement._get_active_subscription(tenant_id)
    plan = sub.plan

    rooms_usage = [
        PropertyRoomUsage(property_id=pid, rooms=ResourceLimit(max=r.max, used=r.used))
        for pid, r in usage.rooms_per_property.items()
    ]

    return {
        "success": True,
        "data": SubscriptionUsageResponse(
            plan_name=plan.name,
            plan_slug=plan.slug,
            status=sub.status.value,
            billing_cycle=sub.billing_cycle.value,
            expires_at=sub.expires_at.isoformat() if sub.expires_at else None,
            properties=ResourceLimit(max=usage.properties.max, used=usage.properties.used),
            staff=ResourceLimit(max=usage.staff.max, used=usage.staff.used),
            rooms_per_property=rooms_usage,
            bookings_this_month=ResourceLimit(
                max=usage.bookings_this_month.max,
                used=usage.bookings_this_month.used,
            ),
            features=usage.features,
        ),
    }
