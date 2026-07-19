from fastapi import Depends, BackgroundTasks
from app.modules.auth.repositories.guests_repo import GuestRepository
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.services.guests_services import GuestService
from app.modules.auth.services.users_services import UserService
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
