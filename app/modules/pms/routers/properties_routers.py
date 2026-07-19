import uuid

from fastapi import APIRouter, Depends, status, Query

from app.modules.auth.auth_middlewares import CurrentUser
from app.modules.pms.dependencies import get_property_service
from app.modules.pms.schemas.properties_schemas import (
    GeneralPropertyInfo,
    GeneralPropertyInfoResponse,
    Location,
    LocationResponse,
    PropertyPhotosAndAmenities,
    PropertyPhotosAndAmenitiesResponse,
    Propertylocalization,
    PropertylocalizationResponse,
    BrandVisual,
    BrandVisualResponse,
    TenantPropertiesListResponse,
    SystemAmenitiesListResponse,
    PropertyResponse,
)
from app.modules.pms.services.properties_scervices import PropertyService
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(prefix="/properties", tags=["Property Management System"])


@router.get(
    "/",
    response_model=StandardResponse[TenantPropertiesListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all properties for a tenant",
)
async def get_tenant_properties(
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0, description="Number of properties to skip"),
    limit: int = Query(default=20, ge=1, le=50, description="Max properties to return"),
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.get_tenant_properties_list(tenant_id, skip, limit)
    return {"success": True, "data": response}


@router.get(
    "/amenities",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[SystemAmenitiesListResponse],
)
async def get_amenities(
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    response = await property_service.get_all_system_amenities()
    return {"success": True, "data": response}


@router.post(
    "/general-information",
    response_model=StandardResponse[GeneralPropertyInfoResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_general_information(
    payload: GeneralPropertyInfo,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    response = await property_service.create_general_information(
        payload=payload, tenant_id=tenant_id
    )
    return {"success": True, "data": response}


@router.get(
    "/{property_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[PropertyResponse],
)
async def get_property_by_id(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.get_property_by_id(property_id, tenant_id)
    return {"success": True, "data": response}


@router.delete(
    "/{property_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse,
)
async def delete_property(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    await property_service.delete_property(property_id, tenant_id)
    return {"success": True, "data": "Property deleted successfully"}


@router.post(
    "/{property_id}/create-location",
    response_model=StandardResponse[LocationResponse],
    status_code=status.HTTP_200_OK,
)
async def create_location(
    property_id: uuid.UUID,
    payload: Location,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.create_location(property_id, payload, tenant_id)
    return {"success": True, "data": response}


@router.post(
    "/{property_id}/create-photos-and-amenities",
    response_model=StandardResponse[PropertyPhotosAndAmenitiesResponse],
    status_code=status.HTTP_200_OK,
)
async def create_photos_and_amenities(
    property_id: uuid.UUID,
    payload: PropertyPhotosAndAmenities,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.create_photos_and_amenities(
        property_id, payload, tenant_id
    )
    return {"success": True, "data": response}


@router.post(
    "/{property_id}/create-localization",
    response_model=StandardResponse[PropertylocalizationResponse],
    status_code=status.HTTP_200_OK,
)
async def create_localization(
    property_id: uuid.UUID,
    payload: Propertylocalization,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.create_localization(
        property_id, payload, tenant_id
    )
    return {"success": True, "data": response}


@router.post(
    "/{property_id}/create-brand-visual",
    response_model=StandardResponse[BrandVisualResponse],
    status_code=status.HTTP_200_OK,
)
async def create_brand_visual(
    property_id: uuid.UUID,
    payload: BrandVisual,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.create_brand_visual(
        property_id, payload, tenant_id
    )
    return {"success": True, "data": response}
