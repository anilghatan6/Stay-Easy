import uuid
from fastapi import APIRouter, Depends, Request

from app.middlewares.auth_middlewares import CurrentSuperAdmin
from app.modules.superadmin.schemas.feature_flag_schemas import (
    CreateFeatureFlagRequest,
    UpdateFeatureFlagRequest,
    FeatureFlagResponse,
    FeatureFlagListResponse,
)
from app.modules.superadmin.services.feature_flag_service import FeatureFlagService
from app.modules.superadmin.dependencies import get_feature_flag_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin - Feature Flags"])


@router.post(
    "/feature-flags",
    response_model=StandardResponse[FeatureFlagResponse],
    summary="Create a feature flag",
)
async def create_feature_flag(
    payload: CreateFeatureFlagRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    feature_flag_service: FeatureFlagService = Depends(get_feature_flag_service),
):
    flag = await feature_flag_service.create_flag(
        name=payload.name,
        key=payload.key,
        description=payload.description,
        is_enabled=payload.is_enabled,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=FeatureFlagResponse.model_validate(flag))


@router.get(
    "/feature-flags",
    response_model=StandardResponse[FeatureFlagListResponse],
    summary="List all feature flags",
)
async def list_feature_flags(
    staff: CurrentSuperAdmin,
    feature_flag_service: FeatureFlagService = Depends(get_feature_flag_service),
):
    flags = await feature_flag_service.list_flags()
    return StandardResponse(
        data=FeatureFlagListResponse(
            flags=[FeatureFlagResponse.model_validate(f) for f in flags],
            total=len(flags),
        )
    )


@router.patch(
    "/feature-flags/{flag_id}",
    response_model=StandardResponse[FeatureFlagResponse],
    summary="Update a feature flag",
)
async def update_feature_flag(
    flag_id: uuid.UUID,
    payload: UpdateFeatureFlagRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    feature_flag_service: FeatureFlagService = Depends(get_feature_flag_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    flag = await feature_flag_service.update_flag(
        flag_id=flag_id,
        update_data=update_data,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=FeatureFlagResponse.model_validate(flag))


@router.delete(
    "/feature-flags/{flag_id}",
    summary="Delete a feature flag",
)
async def delete_feature_flag(
    flag_id: uuid.UUID,
    request: Request,
    staff: CurrentSuperAdmin,
    feature_flag_service: FeatureFlagService = Depends(get_feature_flag_service),
):
    await feature_flag_service.delete_flag(
        flag_id=flag_id,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data={"message": "Feature flag deleted successfully"})
