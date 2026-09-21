import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.middlewares.auth_middlewares import CurrentSuperAdmin
from app.modules.auth.schemas.users_schema import UserResponse
from app.modules.superadmin.schemas.admin_schemas import (
    CreateAdminRequest,
    UpdateAdminRequest,
    AdminResponse,
    AdminListResponse,
    AuditLogResponse,
    AuditLogListResponse,
    ImpersonateResponse,
)
from app.modules.superadmin.services.admin_service import AdminService
from app.modules.superadmin.services.audit_service import AuditService
from app.modules.superadmin.dependencies import get_admin_service, get_audit_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin"])


@router.get("/me", response_model=StandardResponse[UserResponse])
async def me(superadmin: CurrentSuperAdmin):
    return StandardResponse(data=UserResponse.model_validate(superadmin))
    

@router.get(
    "/admins",
    response_model=StandardResponse[AdminListResponse],
    summary="List all admin accounts",
)
async def list_admins(
    staff: CurrentSuperAdmin,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_service: AdminService = Depends(get_admin_service),
):
    admins, total = await admin_service.list_admins(skip=skip, limit=limit)
    return StandardResponse(
        data=AdminListResponse(
            admins=[AdminResponse.model_validate(a) for a in admins],
            total=total,
            skip=skip,
            limit=limit,
        )
    )


@router.post(
    "/admins",
    response_model=StandardResponse[AdminResponse],
    summary="Create a new admin account",
)
async def create_admin(
    payload: CreateAdminRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    admin_service: AdminService = Depends(get_admin_service),
):
    admin = await admin_service.create_admin(
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=AdminResponse.model_validate(admin))


@router.get(
    "/admins/{admin_id}",
    response_model=StandardResponse[AdminResponse],
    summary="Get admin details",
)
async def get_admin(
    admin_id: uuid.UUID,
    staff: CurrentSuperAdmin,
    admin_service: AdminService = Depends(get_admin_service),
):
    admin = await admin_service.get_admin(admin_id)
    return StandardResponse(data=AdminResponse.model_validate(admin))


@router.patch(
    "/admins/{admin_id}",
    response_model=StandardResponse[AdminResponse],
    summary="Update admin account",
)
async def update_admin(
    admin_id: uuid.UUID,
    payload: UpdateAdminRequest,
    request: Request,
    staff: CurrentSuperAdmin,
    admin_service: AdminService = Depends(get_admin_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    admin = await admin_service.update_admin(
        admin_id=admin_id,
        update_data=update_data,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=AdminResponse.model_validate(admin))


@router.delete(
    "/admins/{admin_id}",
    summary="Soft-delete admin account",
)
async def delete_admin(
    admin_id: uuid.UUID,
    request: Request,
    staff: CurrentSuperAdmin,
    admin_service: AdminService = Depends(get_admin_service),
):
    await admin_service.delete_admin(
        admin_id=admin_id,
        actor=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data={"message": "Admin deleted successfully"})


@router.get(
    "/admins/{admin_id}/audit",
    response_model=StandardResponse[AuditLogListResponse],
    summary="Get audit trail for an admin",
)
async def get_admin_audit(
    admin_id: uuid.UUID,
    staff: CurrentSuperAdmin,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    audit_service: AuditService = Depends(get_audit_service),
):
    logs, total = await audit_service.get_logs_for_target(
        target_type="user", target_id=admin_id, skip=skip, limit=limit
    )
    return StandardResponse(
        data=AuditLogListResponse(
            logs=[AuditLogResponse.model_validate(l) for l in logs],
            total=total,
            skip=skip,
            limit=limit,
        )
    )


@router.post(
    "/admins/{admin_id}/impersonate",
    response_model=StandardResponse[ImpersonateResponse],
    summary="Impersonate an admin account",
)
async def impersonate_admin(
    admin_id: uuid.UUID,
    request: Request,
    staff: CurrentSuperAdmin,
    admin_service: AdminService = Depends(get_admin_service),
):
    result = await admin_service.impersonate_admin(
        target_admin_id=admin_id,
        superadmin=staff,
        ip_address=request.client.host if request.client else None,
    )
    return StandardResponse(data=ImpersonateResponse(**result))


@router.get(
    "/audit-logs",
    response_model=StandardResponse[AuditLogListResponse],
    summary="Get all platform audit logs",
)
async def get_all_audit_logs(
    staff: CurrentSuperAdmin,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    audit_service: AuditService = Depends(get_audit_service),
):
    logs, total = await audit_service.get_all_logs(skip=skip, limit=limit)
    return StandardResponse(
        data=AuditLogListResponse(
            logs=[AuditLogResponse.model_validate(l) for l in logs],
            total=total,
            skip=skip,
            limit=limit,
        )
    )
