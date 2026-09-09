import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status, Query

from app.middlewares.auth_middlewares import CurrentUser, CurrentStaff
from app.modules.pms.dependencies import get_property_service
from app.modules.pms.schemas.properties_schemas import (
    TenantPropertiesListResponse,
    SystemAmenitiesListResponse,
    PropertyResponse,
    PropertyBookingsResponse,
    UpdatePropertyInfo,
    SpecificPropertyResponse,
    CreatePropertyRequest
)
from app.modules.pms.services.properties_scervices import PropertyService
from app.modules.booking.models.booking_model import (
    MasterBookingStatus,
    PaymentGateway,
    PaymentStatus,
    PaymentMethod,
    BookingType,
)
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(prefix="/properties", tags=["Property Management System"])


@router.get(
    "",
    response_model=StandardResponse[TenantPropertiesListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all properties for a tenant",
)
async def get_tenant_properties(
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0, description="Number of properties to skip"),
    limit: int = Query(default=10, ge=1, le=50, description="Max properties to return"),
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    properties_list, total_count = await property_service.get_tenant_properties_list(tenant_id, skip, limit)
    has_more = skip + len(properties_list.properties) < total_count
    return {"success": True, "data": properties_list, "meta": {"total": total_count, "skip": skip, "limit": limit, "has_more": has_more}}


@router.post(
    "",
    response_model=StandardResponse[PropertyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_property(
    payload: CreatePropertyRequest,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    response = await property_service.create_property(
        payload=payload, tenant_id=tenant_id
    )
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

@router.patch(
    "/{property_id}",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[PropertyResponse],
)
async def update_property_by_id(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    payload: UpdatePropertyInfo,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.update_property_by_id(property_id, tenant_id, payload)
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


@router.get(
    "/{property_id}/public",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[SpecificPropertyResponse],
)
async def get_specific_property(
    property_id: uuid.UUID,
    property_service: PropertyService = Depends(get_property_service),
):
    response = await property_service.get_specific_property(property_id)

    return {"success": True, "data": response}


@router.post(
    "/{property_id}/toggle-property-activation",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[str],
)
async def toggle_property_activation(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.toggle_property_activation(property_id, tenant_id)
    return response


@router.get(
    "/{property_id}/number-of-floors",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[dict[str, int]],
)
async def get_number_of_floors(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await property_service.get_number_of_floors(property_id, tenant_id)
    return {"success": True, "data": response}


@router.get(
    "/{property_id}/bookings",
    response_model=StandardResponse[list[PropertyBookingsResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_property_bookings(
    property_id: uuid.UUID,
    current_user: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of bookings to skip"),
    limit: int = Query(default=10, ge=1, le=50, description="Max bookings to return"),
    status: Optional[MasterBookingStatus] = Query(default=None, description="Filter by booking status"),
    payment_status: Optional[PaymentStatus] = Query(default=None, description="Filter by payment status"),
    payment_method: Optional[PaymentMethod] = Query(default=None, description="Filter by payment method"),
    payment_gateway: Optional[PaymentGateway] = Query(default=None, description="Filter by payment gateway"),
    booking_type: Optional[BookingType] = Query(default=None, description="Filter by booking type"),
    property_service: PropertyService = Depends(get_property_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response, total_count = await property_service.get_property_bookings(
        property_id, tenant_id, skip, limit,
        status=status,
        payment_status=payment_status,
        payment_method=payment_method,
        payment_gateway=payment_gateway,
        booking_type=booking_type,
    )
    has_more = skip + len(response) < total_count
    return {
        "success": True,
        "data": response,
        "meta": {
            "total": total_count, "skip": skip, "limit": limit, "has_more": has_more
        },
    }
