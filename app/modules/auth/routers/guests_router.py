from fastapi import APIRouter, Depends, status
from app.modules.auth.services.guests_services import GuestService
from app.modules.auth.dependencies import get_guest_service
from app.modules.auth.schemas.guests_schema import (
    GuestCreate,
    GuestResponse,
    GuestProfileUpdate,
)

# from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from app.modules.auth.schemas.token_schema import (
    # Token,
    VerifyOTP,
    ResendOTP,
    RefreshTokenRequest,
    AccessTokenResponse,
)
from app.middlewares.auth_middlewares import CurrentGuest
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit


router = APIRouter(prefix="/auth/guests", tags=["guests"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="guest/register")),
    ],
)
async def register_guest(
    guest: GuestCreate,
    guest_service: Annotated[GuestService, Depends(get_guest_service)],
):
    guest_data = await guest_service.register_guest(guest.model_dump())
    return {
        "message": "Guest registered successfully. Please verify your email.",
        "guest_id": guest_data.id,
        "email": guest_data.email,
    }


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=10, window_seconds=60, scope="guest/verify-otp")),
    ],
)
async def verify_otp(
    otp: VerifyOTP,
    guest_service: Annotated[GuestService, Depends(get_guest_service)],
):
    return await guest_service.verify_registration_otp(otp.email, otp.otp)


@router.post(
    "/resend-otp",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=10, window_seconds=60, scope="guest/resend-otp")),
    ],
)
async def resend_otp(
    resend_data: ResendOTP,
    guest_service: Annotated[GuestService, Depends(get_guest_service)],
):
    await guest_service.resend_registration_otp(resend_data.email)
    return {"message": "Verification code resent successfully."}


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=20, window_seconds=60, scope="guest/refresh")),
    ],
)
async def refresh_token(
    refresh_token: RefreshTokenRequest,
    guest_service: Annotated[GuestService, Depends(get_guest_service)],
):
    return await guest_service.refresh_token(refresh_token.refresh_token)


@router.get(
    "/me",
    response_model=GuestResponse,
    status_code=status.HTTP_200_OK,
)
async def get_current_guest(
    guest: CurrentGuest,
):
    return guest


@router.patch(
    "/me",
    response_model=GuestResponse,
    status_code=status.HTTP_200_OK,
)
async def update_current_guest(
    update_data: GuestProfileUpdate,
    guest: CurrentGuest,
    guest_service: Annotated[GuestService, Depends(get_guest_service)],
):
    updated_guest = await guest_service.update_guest_profile(
        str(guest.id), update_data.model_dump(exclude_unset=True)
    )
    return updated_guest
