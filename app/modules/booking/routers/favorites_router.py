# app/modules/favorites/router.py

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.modules.booking.services.favorites_services import FavoriteService
from app.middlewares.auth_middlewares import CurrentGuest # your existing auth dependency
from app.utils.schemas import StandardResponse
from app.modules.pms.schemas.properties_schemas import PropertyResponse

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.post("/{property_id}/toggle", response_model=StandardResponse)
async def toggle_favorite(
    property_id: uuid.UUID,
    current_guest:CurrentGuest,
    db: AsyncSession = Depends(get_db),
):
    service = FavoriteService(db)
    response = await service.toggle_favorite(current_guest.id, property_id)
    return {
        "success": True,
        "data": response
    }


@router.get("",response_model=StandardResponse[list[PropertyResponse]])
async def list_favorites(
    current_guest:CurrentGuest,
    db: AsyncSession = Depends(get_db),
):
    service = FavoriteService(db)
    response = await service.list_favorites(current_guest.id)
    return {
        "success": True,
        "data": response
    }