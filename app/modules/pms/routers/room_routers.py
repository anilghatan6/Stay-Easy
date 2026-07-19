import uuid

from fastapi import APIRouter, Depends, status

from app.modules.auth.auth_middlewares import CurrentUser
from app.modules.pms.dependencies import get_room_service
from app.modules.pms.schemas.room_schemas import (
    RoomBulkCreateRequest,
    RoomBulkCreateResponse,
    RoomTypeCreate,
    BedTypeCreate,
    RoomTypeResponse,
    BedTypeResponse,
    RoomResponse,
)

from app.modules.pms.services.room_services import RoomService
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(prefix="/properties/{property_id}/rooms", tags=["Rooms"])


@router.get(
    "",
    response_model=StandardResponse[list[RoomResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get all rooms for a property",
)
async def get_rooms(
    property_id: uuid.UUID,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[list[RoomResponse]]:
    verify_tenant(user)
    response = await room_service.get_all_rooms(
        property_id=property_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": response}


@router.post(
    "",
    response_model=StandardResponse[RoomBulkCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create one or more rooms for a property",
)
async def create_rooms(
    property_id: uuid.UUID,
    payload: RoomBulkCreateRequest,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[RoomBulkCreateResponse]:

    verify_tenant(user)
    response = await room_service.create_rooms(
        property_id=property_id,
        tenant_id=user.tenant_id,
        payload=payload,
    )
    return {"success": True, "data": response}


@router.delete(
    "/{room_id}",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete a room",
)
async def delete_room(
    property_id: uuid.UUID,
    room_id: uuid.UUID,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[dict]:
    verify_tenant(user)
    response = await room_service.delete_room(
        property_id=property_id,
        tenant_id=user.tenant_id,
        room_id=room_id,
    )
    return {"success": True, "data": response}

@router.post(
    "/room-type",
    response_model=StandardResponse[RoomTypeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a room type",
)
async def create_room_type(
    property_id: uuid.UUID,
    payload: RoomTypeCreate,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[RoomTypeResponse]:
    verify_tenant(user)
    response = await room_service.create_room_type(
        property_id=property_id,
        tenant_id=user.tenant_id,
        payload=payload,
    )
    return {"success": True, "data": response}


@router.post(
    "/bed-type",
    response_model=StandardResponse[BedTypeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a bed type",
)
async def create_bed_type(
    property_id: uuid.UUID,
    payload: BedTypeCreate,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[BedTypeResponse]:
    verify_tenant(user)
    response = await room_service.create_bed_type(
        property_id=property_id,
        tenant_id=user.tenant_id,
        payload=payload,
    )
    return {"success": True, "data": response}


@router.get(
    "/room-types",
    response_model=StandardResponse[list[RoomTypeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get all room types",
)
async def get_all_room_types(
    property_id: uuid.UUID,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[list[RoomTypeResponse]]:
    verify_tenant(user)
    response = await room_service.get_all_room_types(
        property_id=property_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": response}


@router.get(
    "/bed-types",
    response_model=StandardResponse[list[BedTypeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get all bed types",
)
async def get_all_bed_types(
    property_id: uuid.UUID,
    user: CurrentUser,
    room_service: RoomService = Depends(get_room_service),
) -> StandardResponse[list[BedTypeResponse]]:
    verify_tenant(user)
    response = await room_service.get_all_bed_types(
        property_id=property_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": response}
