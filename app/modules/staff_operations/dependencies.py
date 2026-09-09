from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config.database_config import get_db
from app.config.redis_config import get_redis_client
from app.modules.staff_operations.repository import StaffOperationsRepository
from app.modules.staff_operations.service import StaffOperationsService
from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository


def get_staff_operations_service(
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis_client),
) -> StaffOperationsService:
    staff_ops_repo = StaffOperationsRepository(db)
    booking_repo = BookingRepository(db)
    room_repo = RoomRepository(db)
    property_repo = PropertyRepository(db)
    offer_repo = SpecialOfferRepository(db)
    discount_code_repo = DiscountCodeRepository(db)
    return StaffOperationsService(
        db=db,
        staff_ops_repo=staff_ops_repo,
        booking_repo=booking_repo,
        room_repo=room_repo,
        property_repo=property_repo,
        offer_repo=offer_repo,
        discount_code_repo=discount_code_repo,
        redis_client=redis_client,
    )
