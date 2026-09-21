import uuid
from typing import Optional
from datetime import datetime, timedelta, UTC

from app.modules.superadmin.repositories.admin_repository import AdminRepository
from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.models.users_model import User
from app.utils.exceptions import (
    ServiceException,
    UserAlreadyExistsException,
    UserNotFoundException,
    RepositoryException,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class AdminService:
    def __init__(
        self,
        db,
        admin_repo: AdminRepository,
        audit_repo: AuditRepository,
        auth_service: AuthService,
    ):
        self.db = db
        self.admin_repo = admin_repo
        self.audit_repo = audit_repo
        self.auth_service = auth_service

    async def create_admin(
        self,
        email: str,
        full_name: str,
        phone: Optional[str],
        password: str,
        actor: User,
        ip_address: Optional[str] = None,
    ) -> User:
        existing = await self.admin_repo.get_by_email(email)
        if existing:
            raise UserAlreadyExistsException(
                f"A user with email {email} already exists"
            )

        hashed_password = self.auth_service.get_password_hash(password)
        admin = await self.admin_repo.create_admin(
            email=email,
            full_name=full_name,
            phone=phone,
            hashed_password=hashed_password,
        )

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="create_admin",
            target_type="user",
            target_id=admin.id,
            details={"email": email, "full_name": full_name},
            ip_address=ip_address,
        )

        await self.db.commit()
        logger.info(f"[AdminService] Admin created: {admin.id} by {actor.email}")
        return admin

    async def get_admin(self, admin_id: uuid.UUID) -> User:
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise UserNotFoundException("Admin not found")
        return admin

    async def update_admin(
        self,
        admin_id: uuid.UUID,
        update_data: dict,
        actor: User,
        ip_address: Optional[str] = None,
    ) -> User:
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise UserNotFoundException("Admin not found")

        old_data = {
            "full_name": admin.full_name,
            "phone": admin.phone,
            "is_active": admin.is_active,
        }

        updated = await self.admin_repo.update_admin(admin_id, update_data)
        if updated is None:
            raise UserNotFoundException("Admin not found")

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="update_admin",
            target_type="user",
            target_id=admin_id,
            details={"before": old_data, "after": update_data},
            ip_address=ip_address,
        )

        await self.db.commit()
        logger.info(f"[AdminService] Admin updated: {admin_id} by {actor.email}")
        return updated

    async def delete_admin(
        self,
        admin_id: uuid.UUID,
        actor: User,
        ip_address: Optional[str] = None,
    ):
        admin = await self.admin_repo.get_by_id(admin_id)
        if admin is None:
            raise UserNotFoundException("Admin not found")

        deleted = await self.admin_repo.delete_admin(admin_id)

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="delete_admin",
            target_type="user",
            target_id=admin_id,
            details={"email": admin.email},
            ip_address=ip_address,
        )

        await self.db.commit()
        logger.info(f"[AdminService] Admin deleted: {admin_id} by {actor.email}")

    async def list_admins(self, skip: int = 0, limit: int = 50):
        return await self.admin_repo.list_admins(skip, limit)

    async def impersonate_admin(
        self,
        target_admin_id: uuid.UUID,
        superadmin: User,
        ip_address: Optional[str] = None,
    ) -> dict:
        target = await self.admin_repo.get_by_id(target_admin_id)
        if target is None:
            raise UserNotFoundException("Target admin not found")
        if not target.is_active:
            raise ServiceException("Cannot impersonate an inactive admin")
        if target.role == "superadmin":
            raise ServiceException("Cannot impersonate another superadmin")

        token_data = {
            "sub": str(target.id),
            "role": str(target.role).lower(),
            "impersonator_id": str(superadmin.id),
        }
        expires_in = 900  # 15 minutes
        expire = datetime.now(UTC) + timedelta(seconds=expires_in)
        token_data["exp"] = expire

        import jwt
        from app.config.settings_config import settings

        access_token = jwt.encode(
            token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        await self.audit_repo.log(
            actor_id=superadmin.id,
            actor_email=superadmin.email,
            action="impersonate_admin",
            target_type="user",
            target_id=target_admin_id,
            details={
                "target_email": target.email,
                "target_role": target.role,
                "expires_in": expires_in,
            },
            ip_address=ip_address,
        )

        await self.db.commit()
        logger.info(
            f"[AdminService] Impersonation started: {superadmin.email} -> {target.email}"
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "impersonated_admin_id": target.id,
            "impersonated_admin_email": target.email,
        }
