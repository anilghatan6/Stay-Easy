import uuid

from fastapi import HTTPException, status
from app.modules.auth.auth_middlewares import CurrentUser

def verify_tenant(user:CurrentUser):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to perform this action. You should have a tenant.",
        )
        