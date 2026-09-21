from fastapi import APIRouter, Depends

from app.middlewares.auth_middlewares import CurrentSuperAdmin
from app.modules.superadmin.services.subscription_service import SubscriptionService
from app.modules.superadmin.services.dashboard_service import DashboardService
from app.modules.superadmin.dependencies import get_subscription_service, get_dashboard_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin - Dashboard"])


@router.get(
    "/dashboard",
    summary="Get platform dashboard metrics",
    operation_id="sa_dashboard_metrics_v1",
)
async def get_dashboard(
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    metrics = await subscription_service.get_dashboard_metrics()
    return StandardResponse(data=metrics)


@router.get(
    "/health",
    summary="Get system health status",
    operation_id="sa_system_health_v1",
)
async def get_health(
    staff: CurrentSuperAdmin,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    health = await dashboard_service.get_health()
    return StandardResponse(data=health)
