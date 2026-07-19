from app.modules.pms.repositories.tenants_repo import TenantRepository
from app.utils.exceptions import (
    RepositoryException,
    ServiceException,
    TenantNotFoundException,
    TenantAlreadyExistsException,
)
from app.utils.logging import LoggerFactory
import uuid
from app.modules.pms.models.tenants_model import Tenant

logger = LoggerFactory.get_logger(__name__)


class TenantService:
    def __init__(self, tenant_repo: TenantRepository):
        self.tenant_repo = tenant_repo

    async def create_tenant(self, tenant: dict, owner_id: uuid.UUID) -> Tenant:
        logger.info(f"[TenantService] Creating tenant: {tenant}")
        tenant_data = tenant
        if "name" in tenant_data and tenant_data["name"]:
            tenant_data["slug"] = tenant_data["name"].lower().replace(" ", "-")
        tenant_data["owner_id"] = owner_id

        try:
            tenant_exists = await self.tenant_repo.get_tenant_by_owner_id(
                owner_id=owner_id,
            )
            if tenant_exists:
                logger.error("[TenantService] Tenant already exists")
                raise TenantAlreadyExistsException(
                    f"Tenant with name {tenant_data['name']} already exists"
                )
            new_tenant = await self.tenant_repo.create_tenant(tenant_data)
            logger.info("[TenantService] Tenant created successfully")
            return new_tenant

        except (TenantAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error creating tenant: {str(e)}")
            raise ServiceException(str(e))

    async def get_tenant_by_owner_id(self, owner_id: uuid.UUID) -> Tenant:
        logger.info(f"[TenantService] Getting tenant by owner id: {owner_id}")
        try:
            tenant = await self.tenant_repo.get_tenant_by_owner_id(owner_id)
            if not tenant:
                logger.error("[TenantService] Tenant not found")
                raise TenantNotFoundException(
                    f"Tenant with owner id {owner_id} not found"
                )
            logger.info("[TenantService] Tenant found")
            return tenant
        except (TenantNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error getting tenant by owner id: {str(e)}")
            raise ServiceException(str(e))

    async def get_tenant_by_id(
        self, tenant_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Tenant:
        logger.info(f"[TenantService] Getting tenant by id: {tenant_id}")
        try:
            tenant = await self.tenant_repo.get_tenant_by_id(tenant_id)
            if not tenant:
                logger.error("[TenantService] Tenant not found")
                raise TenantNotFoundException(f"Tenant with id {tenant_id} not found")
            if tenant.owner_id != owner_id:
                logger.error("[TenantService] Tenant not found")
                raise TenantNotFoundException(f"Tenant with id {tenant_id} not found")
            logger.info("[TenantService] Tenant found")
            return tenant
        except (TenantNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error getting tenant by id: {str(e)}")
            raise ServiceException(str(e))

    async def update_user_tenant_id(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        logger.info(f"[TenantService] Updating tenant id for user: {user_id}")
        try:
            result = await self.tenant_repo.update_user_tenant_id(user_id, tenant_id)
            if not result:
                logger.error("[TenantService] Error updating tenant id")
                raise ServiceException("Error updating tenant id")
            logger.info("[TenantService] Tenant id updated successfully")
            return True
        except (ServiceException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error updating tenant id: {str(e)}")
            raise ServiceException(str(e))

    async def update_tenant(
        self, tenant_id: uuid.UUID, owner_id: uuid.UUID, data: dict
    ) -> Tenant:
        logger.info(f"[TenantService] Updating tenant: {tenant_id}")
        try:
            tenant = await self.tenant_repo.get_tenant_by_id(tenant_id)
            if not tenant or tenant.owner_id != owner_id:
                raise TenantNotFoundException(f"Tenant {tenant_id} not found")

            if "name" in data and data["name"]:
                data["slug"] = data["name"].lower().replace(" ", "-")

            updated = await self.tenant_repo.update_tenant(tenant_id, data)
            return updated
        except (TenantNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error updating tenant: {str(e)}")
            raise ServiceException(str(e))

    async def delete_tenant(self, tenant_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        logger.info(f"[TenantService] Deleting tenant: {tenant_id}")
        try:
            tenant = await self.tenant_repo.get_tenant_by_id(tenant_id)
            if not tenant or tenant.owner_id != owner_id:
                raise TenantNotFoundException(f"Tenant {tenant_id} not found")

            return await self.tenant_repo.delete_tenant(tenant_id)
        except (TenantNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[TenantService] Error deleting tenant: {str(e)}")
            raise ServiceException(str(e))
