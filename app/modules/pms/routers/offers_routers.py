from app.modules.pms.services.room_services import RoomService
import uuid
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from app.modules.auth.auth_middlewares import CurrentUser
from app.modules.pms.dependencies import get_special_offer_service, get_room_service
from app.modules.pms.schemas.offers_schema import (
    SpecialOffersCreate,
    SpecialOfferResponse,
    SpecialOfferUpdate,
)
from app.utils.schemas import StandardResponse
from app.modules.pms.services.offers_services import SpecialOfferService

router = APIRouter(
    prefix="/properties/{property_id}/special-offers", tags=["Special Offers"]
)


@router.post(
    "/",
    response_model=StandardResponse[List[SpecialOfferResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_special_offers(
    property_id: uuid.UUID,
    payload: SpecialOffersCreate,
    user: CurrentUser,
    offer_service: SpecialOfferService = Depends(get_special_offer_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to create special offers. You must belong to a tenant.",
        )

    saved_models = await offer_service.create_property_offers(
        property_id=property_id, payload=payload
    )

    formatted_offers = [
        SpecialOfferResponse.model_validate(model_row) for model_row in saved_models
    ]

    return {"success": True, "data": formatted_offers}


@router.get(
    "/",
    response_model=StandardResponse[List[SpecialOfferResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_property_special_offers(
    property_id: uuid.UUID,
    user: CurrentUser,
    offer_service: SpecialOfferService = Depends(get_special_offer_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to get special offers. You must belong to a tenant.",
        )

    saved_models = await offer_service.get_all_offers(property_id=property_id)

    formatted_offers = [
        SpecialOfferResponse.model_validate(model_row) for model_row in saved_models
    ]

    return {"success": True, "data": formatted_offers}


@router.get(
    "/{offer_id}",
    response_model=StandardResponse[SpecialOfferResponse],
    status_code=status.HTTP_200_OK,
)
async def get_special_offer(
    property_id: uuid.UUID,
    offer_id: uuid.UUID,
    user: CurrentUser,
    offer_service: SpecialOfferService = Depends(get_special_offer_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to get special offers. You must belong to a tenant.",
        )
    offer = await offer_service.get_offer_by_id(
        offer_id=offer_id, property_id=property_id
    )
    return {"success": True, "data": offer}


@router.patch(
    "/{offer_id}",
    response_model=StandardResponse[SpecialOfferResponse],
    status_code=status.HTTP_200_OK,
)
async def update_special_offer(
    property_id: uuid.UUID,
    offer_id: uuid.UUID,
    payload: SpecialOfferUpdate,
    user: CurrentUser,
    offer_service: SpecialOfferService = Depends(get_special_offer_service),
    room_service: RoomService = Depends(get_room_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to update special offers. You must belong to a tenant.",
        )

    saved_model = await offer_service.update_offer(
        property_id=property_id,
        tenant_id=user.tenant_id,
        offer_id=offer_id,
        payload=payload,
        room_service=room_service,
    )

    formatted_offer = SpecialOfferResponse.model_validate(saved_model)

    return {"success": True, "data": formatted_offer}


@router.delete("/{offer_id}")
async def delete_special_offer(
    property_id: uuid.UUID,
    offer_id: uuid.UUID,
    user: CurrentUser,
    offer_service: SpecialOfferService = Depends(get_special_offer_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to delete special offers. You must belong to a tenant.",
        )

    response = await offer_service.delete_offer(
        property_id=property_id,
        offer_id=offer_id,
    )
    if response:
        return {"success": True, "data": "Offer deleted successfully"}
