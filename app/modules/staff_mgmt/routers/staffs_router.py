import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from app.modules.staff_mgmt.services.staffs_services import StaffService
from app.modules.staff_mgmt.dependencies import get_staff_service
from app.middlewares.auth_middlewares import CurrentUser
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant
from app.modules.staff_mgmt.schemas.staffs_schemas import StaffResponse, CreateStaffRequest, UpdateStaffRequest

router = APIRouter(prefix="/properties/{property_id}/staffs", tags=["Staff Management"])


@router.post("", response_model=StandardResponse[StaffResponse], status_code=status.HTTP_201_CREATED, description="Create a new staff for the property")
async def create_staff(
    property_id:uuid.UUID,
    current_user: CurrentUser,
    payload:CreateStaffRequest,
    staff_service: StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    response = await staff_service.create_staff(
        tenant_id,
        property_id,
        payload
    )

    return {
        "success":True,
        "data":response,
    }


@router.get("", response_model=StandardResponse[list[StaffResponse]], status_code=status.HTTP_200_OK, description="List all staff for the property")
async def list_staff(
    property_id:uuid.UUID,
    current_user:CurrentUser,
    skip:int = Query(0, ge = 0, description = "Number of staff to skip"),
    limit:int = Query(10, ge=1, le=50, description = "Number of staff to return"),
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response, total = await staff_service.list_staff_by_property(
        tenant_id,
        property_id,
        skip, 
        limit
    )

    has_more = skip + len(response) < total
    return {
        "success": True,
        "data": response,
        "meta": {
            "total": total, "skip": skip, "limit": limit, "has_more": has_more
        },
    }

@router.get("/staffs-summary",response_model=StandardResponse, status_code=status.HTTP_200_OK, description="Get a summary of all staff for the property")
async def get_staff_summary(
    property_id:uuid.UUID,
    current_user:CurrentUser,
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    response = await staff_service.get_staff_summary(
        property_id
    )

    return {
        "success":True,
        "data":response,
    }

# get all the housekeeping staffs
@router.get("/housekeeping-staffs", response_model=StandardResponse[list[StaffResponse]], status_code=status.HTTP_200_OK, description="Get all housekeeping staffs")
async def get_housekeeping_staff(
    property_id:uuid.UUID,
    current_user:CurrentUser,
    search: Optional[str] = Query(default=None, description="Search by staff name (case-insensitive)"),
    skip: int = Query(0, ge=0, description="Number of staff to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max staff to return"),
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response, total = await staff_service.get_housekeeping_staff(
        tenant_id,
        property_id,
        search,
        skip,
        limit
    )

    has_more = skip + len(response) < total
    return {
        "success":True,
        "data":response,
        "meta": {
            "total": total, "skip": skip, "limit": limit, "has_more": has_more
        },
    }

@router.get("/{staff_id}", response_model=StandardResponse[StaffResponse], status_code=status.HTTP_200_OK, description="Get a specific staff")
async def get_staff(
    property_id:uuid.UUID,
    staff_id:uuid.UUID,
    current_user:CurrentUser,
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await staff_service.get_staff_by_id(
        tenant_id,
        property_id,
        staff_id
    )

    return {
        "success":True,
        "data":response,
    }
    
@router.patch("/{staff_id}",response_model=StandardResponse[StaffResponse], status_code=status.HTTP_200_OK, description="Update staff information")
async def update_staff(
    property_id:uuid.UUID,
    staff_id:uuid.UUID,
    current_user:CurrentUser,
    payload:UpdateStaffRequest,
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    response = await staff_service.update_staff(
        tenant_id,
        property_id,
        staff_id,
        payload
    )

    return {
        "success":True,
        "data":response,
    }

@router.delete("/{staff_id}",response_model=StandardResponse, status_code=status.HTTP_200_OK, description="Delete staff")
async def delete_staff(
    property_id:uuid.UUID,
    staff_id:uuid.UUID,
    current_user:CurrentUser,
    staff_service:StaffService = Depends(get_staff_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    await staff_service.delete_staff(
        tenant_id,
        property_id,
        staff_id
    )

    return {
        "success":True,
        "data":"Staff deleted successfully",
    }
