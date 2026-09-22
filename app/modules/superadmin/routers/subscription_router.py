import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.middlewares.auth_middlewares import CurrentSuperAdmin
from app.modules.superadmin.schemas.subscription_schemas import (
    CreatePlanRequest,
    UpdatePlanRequest,
    PlanResponse,
    PlanListResponse,
    AssignSubscriptionRequest,
    UpgradeSubscriptionRequest,
    TenantSubscriptionResponse,
)
from app.modules.superadmin.services.subscription_service import SubscriptionService
from app.modules.superadmin.dependencies import get_subscription_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin - Subscriptions"])


@router.post(
    "/plans",
    response_model=StandardResponse[PlanResponse],
    summary="Create a subscription plan",
)
async def create_plan(
    payload: CreatePlanRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    plan = await subscription_service.create_plan(
        data=payload.model_dump(),
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=PlanResponse.model_validate(plan))


@router.get(
    "/plans",
    response_model=StandardResponse[PlanListResponse],
    summary="List all subscription plans",
)
async def list_plans(
    staff: CurrentSuperAdmin,
    include_inactive: bool = Query(False),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    plans = await subscription_service.list_plans(include_inactive=include_inactive)
    return StandardResponse(
        data=PlanListResponse(
            plans=[PlanResponse.model_validate(p) for p in plans],
            total=len(plans),
        )
    )


@router.get(
    "/plans/{plan_id}",
    response_model=StandardResponse[PlanResponse],
    summary="Get plan details",
)
async def get_plan(
    plan_id: uuid.UUID,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    plan = await subscription_service.get_plan(plan_id)
    return StandardResponse(data=PlanResponse.model_validate(plan))


@router.patch(
    "/plans/{plan_id}",
    response_model=StandardResponse[PlanResponse],
    summary="Update a subscription plan",
)
async def update_plan(
    plan_id: uuid.UUID,
    payload: UpdatePlanRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    plan = await subscription_service.update_plan(
        plan_id=plan_id,
        update_data=update_data,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=PlanResponse.model_validate(plan))


@router.delete(
    "/plans/{plan_id}",
    summary="Deactivate a subscription plan",
)
async def deactivate_plan(
    plan_id: uuid.UUID,
    request: Request,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    await subscription_service.deactivate_plan(
        plan_id=plan_id,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data={"message": "Plan deactivated successfully"})


@router.post(
    "/tenants/{tenant_id}/subscription",
    response_model=StandardResponse[TenantSubscriptionResponse],
    summary="Assign a subscription plan to a tenant",
)
async def assign_subscription(
    tenant_id: uuid.UUID,
    payload: AssignSubscriptionRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    sub = await subscription_service.assign_subscription(
        tenant_id=tenant_id,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=TenantSubscriptionResponse.model_validate(sub))


@router.get(
    "/tenants/{tenant_id}/subscription",
    response_model=StandardResponse[TenantSubscriptionResponse],
    summary="Get tenant's subscription",
)
async def get_tenant_subscription(
    tenant_id: uuid.UUID,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    sub = await subscription_service.get_tenant_subscription(tenant_id)
    if sub is None:
        return StandardResponse(data=None, meta={"message": "No subscription found"})
    return StandardResponse(data=TenantSubscriptionResponse.model_validate(sub))


@router.patch(
    "/tenants/{tenant_id}/subscription",
    response_model=StandardResponse[TenantSubscriptionResponse],
    summary="Upgrade or change a tenant's subscription plan",
)
async def upgrade_subscription(
    tenant_id: uuid.UUID,
    payload: UpgradeSubscriptionRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    sub = await subscription_service.upgrade_subscription(
        tenant_id=tenant_id,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=TenantSubscriptionResponse.model_validate(sub))
