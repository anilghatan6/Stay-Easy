# app/modules/favorites/service.py

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.repositories.favorites_repository import FavoriteRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository  # adjust import path
from app.utils.exceptions import ServiceException  # or your actual exceptions module


class FavoriteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.favorite_repo = FavoriteRepository(db)
        self.property_repo = PropertyRepository(db)

    async def toggle_favorite(self, guest_id: uuid.UUID, property_id: uuid.UUID) -> dict:
        try:
            property_obj = await self.property_repo.get_by_id(property_id)
            if property_obj is None:
                raise ServiceException(user_message="Property not found",status_code=404)

            existing = await self.favorite_repo.get(guest_id, property_id)

            if existing:
                await self.favorite_repo.remove(guest_id, property_id)
                await self.db.commit()
                return {"property_id": property_id, "is_favorite": False}

            await self.favorite_repo.add(guest_id, property_id)
            await self.db.commit()
            return {"property_id": property_id, "is_favorite": True}

        except BookingException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise ServiceException("Could not update favorite. Please try again.") from e

    async def list_favorites(self, guest_id: uuid.UUID) -> list:
        favorites = await self.favorite_repo.list_for_guest(guest_id)
        property_ids = [f.property_id for f in favorites]
        # Fetch full property details for display (adjust to your PropertyRepository API)
        return await self.property_repo.get_by_ids(property_ids)