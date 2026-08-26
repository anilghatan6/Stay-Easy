from fastapi import Depends, HTTPException, status
from app.modules.auth.dependencies import get_guest_service, get_user_service
from app.modules.auth.services.guests_services import GuestService

from app.modules.auth.models.guests_model import Guest
from app.modules.auth.models.users_model import User
from app.modules.auth.services.users_services import UserService
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme_guest = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Staff roles allowed to perform check-in/check-out operations
STAFF_ROLES = {"admin","manager", "front_desk"}


async def get_current_guest(
    token: str = Depends(oauth2_scheme_guest),
    guest_service: GuestService = Depends(get_guest_service),
) -> Guest:
    guest = guest_service.auth_service.verify_access_token(token)
    if not guest or guest.get("role") != "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    guest = await guest_service.get_guest_by_id(guest["user_id"])
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if guest.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password",
            headers={"WWW-Authenticate": "Bearer"},
        )
 
    return guest


CurrentGuest = Annotated[Guest, Depends(get_current_guest)]



async def get_current_guest_change_password(
    token: str = Depends(oauth2_scheme_guest),
    guest_service: GuestService = Depends(get_guest_service),
) -> Guest:
    guest = guest_service.auth_service.verify_access_token(token)
    if not guest or guest.get("role") != "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    guest = await guest_service.get_guest_by_id(guest["user_id"])
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
   
    return guest


CurrentGuestChangePassword = Annotated[Guest, Depends(get_current_guest_change_password)]


# =======================================================================================================================================


async def get_current_user(token: str = Depends(oauth2_scheme_user), user_service: UserService = Depends(get_user_service)) -> User:
    user = user_service.auth_service.verify_access_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await user_service.get_user_by_id(user["user_id"])
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
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]



async def get_current_user_change_password(token: str = Depends(oauth2_scheme_user), user_service: UserService = Depends(get_user_service)) -> User:
    user = user_service.auth_service.verify_access_token(token)
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await user_service.get_user_by_id(user["user_id"])
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
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


CurrentUserChangePassword = Annotated[User, Depends(get_current_user_change_password)]


# =======================================================================================================================================
# Staff Authentication — allows MANAGER and FRONT_DESK roles
# =======================================================================================================================================


async def get_current_staff(
    token: str = Depends(oauth2_scheme_user),
    user_service: UserService = Depends(get_user_service),
) -> User:
    payload = user_service.auth_service.verify_access_token(token)
    if not payload or payload.get("role") not in STAFF_ROLES:
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
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentStaff = Annotated[User, Depends(get_current_staff)]

