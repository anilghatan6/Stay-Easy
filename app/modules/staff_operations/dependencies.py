from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config.database_config import get_db
from app.modules.staff_operations.repository import StaffOperationsRepository
from app.modules.staff_operations.service import StaffOperationsService
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository


def get_staff_operations_service(
    db: AsyncSession = Depends(get_db),
) -> StaffOperationsService:
    staff_ops_repo = StaffOperationsRepository(db)
    room_repo = RoomRepository(db)
    offer_repo = SpecialOfferRepository(db)
    return StaffOperationsService(
        db=db, 
        staff_ops_repo=staff_ops_repo, 
        room_repo=room_repo, 
        offer_repo=offer_repo
    )
