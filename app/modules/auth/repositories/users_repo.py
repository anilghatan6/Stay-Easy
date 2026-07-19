from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.modules.auth.models.users_model import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory
import uuid

logger = LoggerFactory.get_logger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_user(self, user: dict) -> User:
        logger.info("[UserRepository] Creating user")
        try:
            new_user = User(**user)
            self.session.add(new_user)
            await self.session.commit()
            await self.session.refresh(new_user)
            logger.info("[UserRepository] User created successfully")
            return new_user

        except IntegrityError as e:
            logger.error(f"[UserRepository] Error creating user: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(
                user_message="User already exists",
                internal_detail=f"Integrity error: {str(e)}",
                status_code=409,
            )

        except SQLAlchemyError as e:
            logger.error(f"[UserRepository] Error creating user: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"SQLAlchemy error: {str(e)}")

        except Exception as e:
            logger.error(f"[UserRepository] Error creating user: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"Error creating user: {str(e)}")

    async def get_user_by_email(self, email: str) -> User | None:
        logger.info("[UserRepository] Getting user by email")
        try:
            result = await self.session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            return user
            
        except Exception as e:
            logger.error(f"[UserRepository] Error getting user by email: {str(e)}")
            raise RepositoryException(
                internal_detail=f"Error getting user by email: {str(e)}"
            )

    async def get_user_by_id(self, user_id: str) -> User | None:
        logger.info("[UserRepository] Getting user by ID")
        try:
            result = await self.session.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(f"[UserRepository] Error getting user by ID: {str(e)}")
            raise RepositoryException(
                internal_detail=f"Error getting user by ID: {str(e)}"
            )

    async def update_user(self, user: User) -> User:
        logger.info(f"[UserRepository] Updating user: {user.id}")
        try:
            stmt = (
                update(User)
                .where(User.id == user.id)
                .values(
                    full_name=user.full_name,
                    phone=user.phone,
                    role=user.role,
                    tenant_id=user.tenant_id,
                    hashed_password=user.hashed_password,
                    is_active=user.is_active,
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info("[UserRepository] User updated successfully")
            return user
        except SQLAlchemyError as e:
            logger.error(f"[UserRepository] Error updating user: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"SQLAlchemy error: {str(e)}")
        except Exception as e:
            logger.error(f"[UserRepository] Error updating user: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"Error updating user: {str(e)}")
