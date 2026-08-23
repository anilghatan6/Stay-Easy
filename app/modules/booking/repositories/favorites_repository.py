# app/modules/favorites/repository.py

import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.models.favourites_model import GuestFavorite


class FavoriteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, guest_id: uuid.UUID, property_id: uuid.UUID) -> GuestFavorite | None:
        result = await self.db.execute(
            select(GuestFavorite).where(
                GuestFavorite.guest_id == guest_id,
                GuestFavorite.property_id == property_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_guest(self, guest_id: uuid.UUID) -> list[GuestFavorite]:
        result = await self.db.execute(
            select(GuestFavorite).where(GuestFavorite.guest_id == guest_id)
        )
        return list(result.scalars().all())

    async def add(self, guest_id: uuid.UUID, property_id: uuid.UUID) -> GuestFavorite:
        favorite = GuestFavorite(guest_id=guest_id, property_id=property_id)
        self.db.add(favorite)
        await self.db.flush()
        return favorite

    async def remove(self, guest_id: uuid.UUID, property_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(GuestFavorite).where(
                GuestFavorite.guest_id == guest_id,
                GuestFavorite.property_id == property_id,
            )
        )