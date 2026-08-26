from fastapi import Depends, HTTPException, status
from typing import Annotated

from app.modules.auth.services.users_services import UserService
from app.modules.auth.dependencies import get_user_service
from app.modules.auth.models.users_model import User
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme_housekeeping = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

HOUSEKEEPING_ROLES = {"housekeeping"}


async def get_current_housekeeping_staff(
    token: str = Depends(oauth2_scheme_housekeeping),
    user_service: UserService = Depends(get_user_service),
) -> User:
    payload = user_service.auth_service.verify_access_token(token)
    if not payload or payload.get("role") not in HOUSEKEEPING_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await user_service.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password",
        )
    return user


CurrentHousekeepingStaff = Annotated[User, Depends(get_current_housekeeping_staff)]
