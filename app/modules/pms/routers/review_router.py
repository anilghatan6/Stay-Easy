import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.middlewares.auth_middlewares import CurrentGuest
from app.modules.pms.dependencies import get_review_service
from app.modules.pms.schemas.review_schemas import (
    PaginatedReviewsResponse,
    ReviewCreateRequest,
    ReviewEditRequest,
    ReviewResponse,
)
from app.modules.pms.services.review_service import ReviewService
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/properties", tags=["reviews"])


@router.post(
    "/{property_id}/reviews",
    status_code=201,
)
async def create_review(
    property_id: uuid.UUID,
    body: ReviewCreateRequest,
    guest: CurrentGuest,
    review_service: Annotated[ReviewService, Depends(get_review_service)],
):
    result = await review_service.create_review(
        property_id=property_id,
        guest=guest,
        booking_id=None,
        rating=body.rating,
        comment=body.comment,
    )
    return StandardResponse(data=ReviewResponse(**result))


@router.patch(
    "/{property_id}/reviews/{review_id}",
    status_code=200,
)
async def edit_review(
    property_id: uuid.UUID,
    review_id: uuid.UUID,
    body: ReviewEditRequest,
    guest: CurrentGuest,
    review_service: Annotated[ReviewService, Depends(get_review_service)],
):
    result = await review_service.edit_review(
        review_id=review_id,
        guest=guest,
        rating=body.rating,
        comment=body.comment,
    )
    return StandardResponse(data=ReviewResponse(**result))


@router.get( "/{property_id}/reviews",
    status_code=200,)
async def get_review(
    guest:CurrentGuest,
    property_id: uuid.UUID,
    review_id: uuid.UUID,
    review_service: Annotated[ReviewService, Depends(get_review_service)],
):
    result = await review_service.get_review(
        property_id=property_id,
        review_id=review_id,
        guest_id=guest.id
    )
    return StandardResponse(data=ReviewResponse(**result))

@router.get(
    "/{property_id}/reviews",
    status_code=200,
)
async def get_reviews_for_property(
    property_id: uuid.UUID,
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
):
    result = await review_service.get_reviews_for_property(
        property_id=property_id,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(data=PaginatedReviewsResponse(**result))
