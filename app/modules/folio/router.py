import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.middlewares.auth_middlewares import CurrentStaff
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit
from app.modules.folio.dependencies import get_folio_service
from app.modules.folio.schemas import (
    AddChargeRequest,
    CreateFolioRequest,
    FolioChargeResponse,
    FolioDetailResponse,
    FolioListResponse,
    FolioResponse,
    UpdateChargeRequest,
    UpdateFolioRequest,
)
from app.modules.folio.service import FolioService
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(prefix="/staff", tags=["folio"])


# ─────────────────────── FOLIO ENDPOINTS ─────────────────────────


@router.post(
    "/properties/{property_id}/bookings/{ref_number}/folio",
    response_model=StandardResponse[FolioDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a folio for a booking",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="folio/create")),
    ],
)
async def create_folio(
    property_id: uuid.UUID,
    ref_number: str,
    staff: CurrentStaff,
    body: CreateFolioRequest = CreateFolioRequest(),
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.create_folio(
        property_id=property_id,
        ref_number=ref_number,
        staff_user=staff,
        tax=body.tax,
        discount=body.discount,
    )
    return StandardResponse(data=FolioDetailResponse(**result))


@router.get(
    "/folios/{folio_id}",
    response_model=StandardResponse[FolioDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get folio details with all charges",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="folio/get")),
    ],
)
async def get_folio(
    folio_id: uuid.UUID,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.get_folio(
        folio_id=folio_id,
        staff_user=staff,
    )
    return StandardResponse(data=FolioDetailResponse(**result))


@router.get(
    "/properties/{property_id}/folios",
    response_model=StandardResponse[FolioListResponse],
    status_code=status.HTTP_200_OK,
    summary="List all folios for a property",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="folio/list")),
    ],
)
async def list_folios(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.list_folios_by_property(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(data=FolioListResponse(**result))


@router.patch(
    "/folios/{folio_id}",
    response_model=StandardResponse[FolioResponse],
    status_code=status.HTTP_200_OK,
    summary="Update folio tax and discount",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="folio/update")),
    ],
)
async def update_folio(
    folio_id: uuid.UUID,
    body: UpdateFolioRequest,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.update_folio(
        folio_id=folio_id,
        staff_user=staff,
        tax=body.tax,
        discount=body.discount,
    )
    return StandardResponse(data=FolioResponse(**result))


@router.post(
    "/folios/{folio_id}/settle",
    response_model=StandardResponse[FolioResponse],
    status_code=status.HTTP_200_OK,
    summary="Settle a folio (mark as PAID)",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=10, window_seconds=60, scope="folio/settle")),
    ],
)
async def settle_folio(
    folio_id: uuid.UUID,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.settle_folio(
        folio_id=folio_id,
        staff_user=staff,
    )
    return StandardResponse(data=FolioResponse(**result))


@router.post(
    "/folios/{folio_id}/waive",
    response_model=StandardResponse[FolioResponse],
    status_code=status.HTTP_200_OK,
    summary="Waive a folio balance",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=10, window_seconds=60, scope="folio/waive")),
    ],
)
async def waive_folio(
    folio_id: uuid.UUID,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.waive_folio(
        folio_id=folio_id,
        staff_user=staff,
    )
    return StandardResponse(data=FolioResponse(**result))


# ─────────────────────── CHARGE ENDPOINTS ─────────────────────────


@router.post(
    "/folios/{folio_id}/charges",
    response_model=StandardResponse[FolioChargeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a charge to a folio",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="folio/add-charge")),
    ],
)
async def add_charge(
    folio_id: uuid.UUID,
    body: AddChargeRequest,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.add_charge(
        folio_id=folio_id,
        staff_user=staff,
        description=body.description,
        amount=body.amount,
        category=body.category,
    )
    return StandardResponse(data=FolioChargeResponse(**result))


@router.get(
    "/folios/{folio_id}/charges",
    response_model=StandardResponse[List[FolioChargeResponse]],
    status_code=status.HTTP_200_OK,
    summary="List all charges for a folio",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="folio/list-charges")),
    ],
)
async def list_charges(
    folio_id: uuid.UUID,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.list_charges(
        folio_id=folio_id,
        staff_user=staff,
    )
    return StandardResponse(data=[FolioChargeResponse(**c) for c in result])


@router.patch(
    "/folios/{folio_id}/charges/{charge_id}",
    response_model=StandardResponse[FolioChargeResponse],
    status_code=status.HTTP_200_OK,
    summary="Update a charge",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="folio/update-charge")),
    ],
)
async def update_charge(
    folio_id: uuid.UUID,
    charge_id: uuid.UUID,
    body: UpdateChargeRequest,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.update_charge(
        folio_id=folio_id,
        charge_id=charge_id,
        staff_user=staff,
        description=body.description,
        amount=body.amount,
        category=body.category,
    )
    return StandardResponse(data=FolioChargeResponse(**result))


@router.delete(
    "/folios/{folio_id}/charges/{charge_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a charge from a folio",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="folio/delete-charge")),
    ],
)
async def delete_charge(
    folio_id: uuid.UUID,
    charge_id: uuid.UUID,
    staff: CurrentStaff,
    folio_service: FolioService = Depends(get_folio_service),
):
    verify_tenant(staff)
    result = await folio_service.delete_charge(
        folio_id=folio_id,
        charge_id=charge_id,
        staff_user=staff,
    )
    return StandardResponse(data=result)
