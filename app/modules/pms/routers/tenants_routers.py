from fastapi import APIRouter, Depends, status, Request
from app.middlewares.auth_middlewares import CurrentUser
from app.modules.pms.schemas.tenant_scheams import (
    TenantCreateSchema,
    TenantResponseSchema,
    TenantUpdateSchema,
)
from app.modules.pms.services.tenant_services import TenantService
from app.modules.pms.dependencies import get_tenant_service
from app.modules.superadmin.dependencies import get_subscription_service
from app.modules.superadmin.services.subscription_service import SubscriptionService
from app.utils.schemas import StandardResponse

FREE_TRIAL_PLAN_ID = "dfc028a9-b67f-438a-84bc-969e2cc33eb8"

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("", response_model=StandardResponse[TenantResponseSchema], status_code=status.HTTP_200_OK)
async def get_tenant(
    current_user: CurrentUser,
    tenant_service: TenantService = Depends(get_tenant_service),
):
    response = await tenant_service.get_tenant_by_id(
        current_user.tenant_id, current_user.id
    )
    return {"success": True, "data": response}


@router.post(
    "", response_model=StandardResponse[TenantResponseSchema], status_code=status.HTTP_201_CREATED
)
async def create_tenant(
    request: Request,
    tenant: TenantCreateSchema,
    current_user: CurrentUser,
    tenant_service: TenantService = Depends(get_tenant_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
):
    new_tenant = await tenant_service.create_tenant(
        tenant.model_dump(), current_user.id
    )
    await tenant_service.update_user_tenant_id(current_user.id, new_tenant.id)

    await subscription_service.assign_subscription(
        tenant_id=new_tenant.id,
        plan_id=FREE_TRIAL_PLAN_ID,
        billing_cycle="MONTHLY",
        actor=current_user,
        ip_address=request.client.host if request.client else None,
    )

    return {"success": True, "data": new_tenant}


@router.patch("", response_model=StandardResponse[TenantResponseSchema])
async def update_tenant(
    tenant_data: TenantUpdateSchema,
    current_user: CurrentUser,
    tenant_service: TenantService = Depends(get_tenant_service),
):
    updated_tenant = await tenant_service.update_tenant(
        current_user.tenant_id,
        current_user.id,
        tenant_data.model_dump(exclude_unset=True),
    )
    return {"success": True, "data": updated_tenant}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    current_user: CurrentUser,
    tenant_service: TenantService = Depends(get_tenant_service),
):
    await tenant_service.delete_tenant(current_user.tenant_id, current_user.id)
    return {"success": True, "message": "Tenant deleted successfully"}
