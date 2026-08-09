from fastapi import APIRouter, Depends, status, BackgroundTasks
from app.modules.auth.services.password_reset_services import PasswordResetService
from app.modules.auth.schemas.password_reset_schema import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from app.modules.auth.dependencies import get_password_reset_service
from app.middlewares.auth_middlewares import (
    CurrentUserChangePassword,
    CurrentGuestChangePassword,
)
from app.utils.schemas import StandardResponse
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=5, window_seconds=60, scope="password_reset")),
    ],
)


@router.post(
    "/forgot-password",
    response_model=StandardResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
):
    background_tasks.add_task(
        password_reset_service.request_password_reset, payload.email
    )
    return StandardResponse(
        success=True,
        data="If an account exists with this email, you will receive password reset instructions.",
    )


# @router.post(
#     "/reset-password",
#     response_model=StandardResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def reset_password(
#     payload: ResetPasswordRequest,
#     password_reset_service: PasswordResetService = Depends(get_password_reset_service),
# ):
#     await password_reset_service.reset_password(payload.token, payload.new_password)
#     return StandardResponse(
#         success=True,
#         data="Password reset successfully.You can now log in with your new password.",
#     )


@router.post(
    "/guest/change-password",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def change_guest_password(
    payload: ChangePasswordRequest,
    current_guest: CurrentGuestChangePassword,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
):
    await password_reset_service.change_password(
        current_guest, payload.current_password, payload.new_password, "guest"
    )
    return StandardResponse(
        success=True,
        data="Password changed successfully.You can now log in with your new password.",
    )


@router.post(
    "/user/change-password",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def change_user_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserChangePassword,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
):
    await password_reset_service.change_password(
        current_user, payload.current_password, payload.new_password, "user"
    )
    return StandardResponse(
        success=True,
        data="Password changed successfully.You can now log in with your new password.",
    )
