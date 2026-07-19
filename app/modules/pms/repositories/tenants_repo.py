from app.modules.pms.models.tenants_model import Tenant
from app.modules.auth.models.users_model import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, update, delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory
import uuid

logger = LoggerFactory.get_logger(__name__)


class TenantRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, tenant: dict) -> Tenant:
        logger.info(f"[TenantsRepoitory] Creating tenant: {tenant}")
        try:
            new_tenant = Tenant(**tenant)
            self.db.add(new_tenant)
            await self.db.commit()
            await self.db.refresh(new_tenant)
            logger.info("[TenantsRepoitory] Tenant created successfully")
            return new_tenant
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error creating tenant: {str(e)}")
            raise RepositoryException(str(e))
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error creating tenant: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error creating tenant: {str(e)}")
            raise RepositoryException(str(e))

    async def get_tenant_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        logger.info(f"[TenantsRepoitory] Getting tenant by id: {tenant_id}")
        try:
            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant:
                logger.info("[TenantsRepoitory] Tenant found")
            else:
                logger.error("[TenantsRepoitory] Tenant not found")
            return tenant

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error getting tenant by id: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            logger.error(f"[TenantsRepoitory] Error getting tenant by id: {str(e)}")
            raise RepositoryException(str(e))

    async def get_tenant_by_owner_id(self, owner_id: uuid.UUID) -> Tenant | None:
        logger.info(f"[TenantsRepoitory] Getting tenant by id: {owner_id}")
        try:
            result = await self.db.execute(
                select(Tenant).where(Tenant.owner_id == owner_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                logger.info("[TenantsRepoitory] Tenant found")
            else:
                logger.error("[TenantsRepoitory] Tenant not found")
            return tenant
        except SQLAlchemyError as e:
            logger.error(f"[TenantsRepoitory] Error getting tenant by id: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            logger.error(f"[TenantsRepoitory] Error getting tenant by id: {str(e)}")
            raise RepositoryException(str(e))

    async def check_existing_tenant(
        self, tenant_name: str, owner_id: uuid.UUID
    ) -> Tenant | None:
        logger.info(
            f"[TenantsRepository] Checking existence for tenant name: '{tenant_name}'"
        )

        try:
            query = select(Tenant).where(
                Tenant.owner_id == owner_id,
                or_(
                    func.lower(Tenant.name) == tenant_name.lower(),
                ),
            )

            result = await self.db.execute(query)
            tenant = result.scalar_one_or_none()

            if tenant:
                logger.info(
                    "[TenantsRepository] Conflict found: Tenant with this name already exists."
                )
            else:
                logger.debug(
                    "[TenantsRepository] No matching tenant found. Safe to proceed."
                )

            return tenant

        except SQLAlchemyError as e:
            logger.error(
                f"[TenantsRepository] Database failure during tenant lookup: {str(e)}"
            )
            raise RepositoryException(str(e))
        except Exception as e:
            logger.error(
                f"[TenantsRepository] Database failure during tenant lookup: {str(e)}"
            )
            raise RepositoryException(
                "A database error occurred while verifying tenant information."
            )

    async def update_user_tenant_id(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        logger.info(f"[TenantsRepoitory] Updating tenant id for user: {user_id}")
        try:
            result = await self.db.execute(
                update(User).where(User.id == user_id).values(tenant_id=tenant_id)
            )
            await self.db.commit()
            if result.rowcount == 1:
                logger.info("[TenantsRepoitory] User updated successfully")
                return True
            else:
                logger.error("[TenantsRepoitory] User not found")
                return False

        except SQLAlchemyError as e:
            logger.error(f"[TenantsRepoitory] Error updating user: {str(e)}")
            await self.db.rollback()
            raise RepositoryException(str(e))
        except Exception as e:
            logger.error(f"[TenantsRepoitory] Error updating user: {str(e)}")
            await self.db.rollback()
            raise RepositoryException(str(e))

    async def update_tenant(self, tenant_id: uuid.UUID, data: dict) -> Tenant | None:
        logger.info(f"[TenantsRepoitory] Updating tenant: {tenant_id}")
        try:
            query = (
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(**data)
                .returning(Tenant)
            )
            result = await self.db.execute(query)
            await self.db.commit()
            return result.scalars().first()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error updating tenant: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error updating tenant: {str(e)}")
            raise RepositoryException(str(e))

    async def delete_tenant(self, tenant_id: uuid.UUID) -> bool:
        logger.info(f"[TenantsRepoitory] Deleting tenant: {tenant_id}")
        try:
            query = delete(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(query)
            await self.db.commit()
            return result.rowcount > 0
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error deleting tenant: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[TenantsRepoitory] Error deleting tenant: {str(e)}")
            raise RepositoryException(str(e))

    async def list_tenants(self) -> list[Tenant]:
        # For superadmin use
        logger.info("[TenantsRepoitory] Listing tenants")
        try:
            result = await self.db.execute(select(Tenant))
            tenants = result.scalars().all()
            logger.info(f"[TenantsRepoitory] {len(tenants)} tenants found")
            return list(tenants)
        except SQLAlchemyError as e:
            logger.error(f"[TenantsRepoitory] Error listing tenants: {str(e)}")
            raise RepositoryException(str(e))
        except Exception as e:
            logger.error(f"[TenantsRepoitory] Error listing tenants: {str(e)}")
            raise RepositoryException(str(e))
