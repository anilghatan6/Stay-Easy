from fastapi import APIRouter, Depends, status
from app.modules.auth.schemas.users_schema import UserCreate, UserResponse
from app.modules.auth.schemas.token_schema import (
    Token,
    VerifyOTP,
    ResendOTP,
    RefreshTokenRequest,
    AccessTokenResponse,
)
from app.modules.auth.services.users_services import UserService
from app.modules.auth.dependencies import get_user_service
from app.modules.auth.auth_middlewares import CurrentUser
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

router = APIRouter(prefix="/auth/users", tags=["Users"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: UserCreate,
    user_service: UserService = Depends(get_user_service),
):
    user_data = await user_service.register_user(user_create.model_dump())
    return {
        "message": "User registered successfully. Please verify your email.",
        "user_id": user_data.id,
        "email": user_data.email,
    }


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(
    verify_data: VerifyOTP,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.verify_registration_otp(
        verify_data.email, verify_data.otp
    )


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_otp(
    resend_data: ResendOTP,
    user_service: UserService = Depends(get_user_service),
):
    await user_service.resend_registration_otp(resend_data.email)
    return {"message": "Verification code resent successfully."}


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    user_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserService = Depends(get_user_service),
):
    user_info = {
        "email": user_data.username ,
        "password": user_data.password,
    }
    return await user_service.login_user(user_info)


@router.post("/refresh", response_model=AccessTokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    refresh_token: RefreshTokenRequest,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.refresh_token(refresh_token.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: CurrentUser) -> UserResponse:
    return current_user
