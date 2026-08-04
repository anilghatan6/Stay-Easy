from fastapi import Depends, BackgroundTasks
from app.modules.auth.repositories.guests_repo import GuestRepository
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.repositories.password_reset_repository import (
    PasswordResetRepository,
)
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.services.guests_services import GuestService
from app.modules.auth.services.users_services import UserService
from app.modules.auth.services.password_reset_services import PasswordResetService
from app.config.database_config import get_db
from app.config.redis_config import get_redis_client
from app.modules.auth.services.otp_service import OTPService


def get_guest_auth_service() -> AuthService:
    return AuthService()


# --- Guest Dependencies ---


def get_guest_repository(db=Depends(get_db)) -> GuestRepository:
    return GuestRepository(db)


def get_otp_service(redis_client=Depends(get_redis_client)) -> OTPService:
    return OTPService(redis_client)


def get_guest_service(
    guest_repository: GuestRepository = Depends(get_guest_repository),
    auth_service: AuthService = Depends(get_guest_auth_service),
    otp_service: OTPService = Depends(get_otp_service),
    background_tasks: BackgroundTasks = BackgroundTasks,
) -> GuestService:
    return GuestService(guest_repository, auth_service, otp_service, background_tasks)


# --- User Dependencies ---


def get_user_repository(db=Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_guest_auth_service),
    otp_service: OTPService = Depends(get_otp_service),
    background_tasks: BackgroundTasks = BackgroundTasks,
) -> UserService:
    return UserService(user_repository, auth_service, otp_service, background_tasks)


def get_password_reset_repository(
    db=Depends(get_db),
) -> PasswordResetRepository:
    return PasswordResetRepository(db)


def get_password_reset_service(
    db=Depends(get_db),
    password_reset_repo=Depends(get_password_reset_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    guest_repo: GuestRepository = Depends(get_guest_repository),
    auth_service: AuthService = Depends(get_guest_auth_service),
) -> PasswordResetService:
    return PasswordResetService(
        db=db,
        password_reset_repo=password_reset_repo,
        user_repo=user_repo,
        guest_repo=guest_repo,
        auth_service=auth_service,
    )
