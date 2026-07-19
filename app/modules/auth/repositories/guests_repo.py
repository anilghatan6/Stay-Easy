from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.modules.auth.models.guests_model import Guest
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory
import uuid

logger = LoggerFactory.get_logger(__name__)


class GuestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_guest(self, guest: dict) -> Guest:
        logger.info("[GuestRepository] Creating guest")
        try:
            new_guest = Guest(**guest)
            self.session.add(new_guest)
            await self.session.commit()
            await self.session.refresh(new_guest)
            logger.info("[GuestRepository] Guest created successfully")
            return new_guest

        except IntegrityError as e:
            logger.error(f"[GuestRepository] Error creating guest: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(
                user_message="Guest already exists",
                internal_detail=f"Integrity error: {str(e)}",
                status_code=409,
            )

        except SQLAlchemyError as e:
            logger.error(f"[GuestRepository] Error creating guest: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"SQLAlchemy error: {str(e)}")

        except Exception as e:
            logger.error(f"[GuestRepository] Error creating guest: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"Error creating guest: {str(e)}")

    async def get_guest_by_email(self, email: str) -> Guest | None:
        logger.info("[GuestRepository] Getting guest by email")
        try:
            result = await self.session.execute(
                select(Guest).where(Guest.email == email)
            )
            guest = result.scalar_one_or_none()
            return guest
        except Exception as e:
            logger.error(f"[GuestRepository] Error getting guest by email: {str(e)}")
            raise RepositoryException(
                internal_detail=f"Error getting guest by email: {str(e)}"
            )

    async def get_guest_by_id(self, guest_id: str) -> Guest | None:
        logger.info("[GuestRepository] Getting guest by ID")
        try:
            result = await self.session.execute(
                select(Guest).where(Guest.id == uuid.UUID(guest_id))
            )
            guest = result.scalar_one_or_none()
            return guest
        except Exception as e:
            logger.error(f"[GuestRepository] Error getting guest by ID: {str(e)}")
            raise RepositoryException(
                internal_detail=f"Error getting guest by ID: {str(e)}"
            )

    async def update_guest(self, guest: Guest) -> Guest:
        logger.info(f"[GuestRepository] Updating guest: {guest.id}")
        try:
            stmt = (
                update(Guest)
                .where(Guest.id == guest.id)
                .values(
                    full_name=guest.full_name,
                    phone=guest.phone,
                    nationality=guest.nationality,
                    password_hash=guest.password_hash,
                    is_active=guest.is_active,
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info("[GuestRepository] Guest updated successfully")
            return await self.get_guest_by_id(str(guest.id))
        except Exception as e:
            logger.error(f"[GuestRepository] Error updating guest: {str(e)}")
            await self.session.rollback()
            raise RepositoryException(internal_detail=f"Error updating guest: {str(e)}")
