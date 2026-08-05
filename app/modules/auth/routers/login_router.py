from fastapi import APIRouter, Depends, status
from app.modules.auth.services.guests_services import GuestService
from app.modules.auth.services.users_services import UserService
from app.modules.auth.dependencies import get_guest_service, get_user_service
from app.modules.auth.schemas.token_schema import Token
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from app.utils.exceptions import UserNotFoundException, AccountInactiveException
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="login")),
    ],
)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(
    credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    guest_service: GuestService = Depends(get_guest_service),
    user_service: UserService = Depends(get_user_service),
):
    login_data = {
        "email": credentials.username.strip(),
        "password": credentials.password.strip(),
    }

    try:
        return await guest_service.login_guest(login_data)
    except (UserNotFoundException, AccountInactiveException):
        pass

    try:
        return await user_service.login_user(login_data)
    except (UserNotFoundException, AccountInactiveException):
        pass

    raise UserNotFoundException("Invalid credentials", "Email/Password mismatch")
