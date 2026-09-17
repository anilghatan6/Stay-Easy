from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config.database_config import get_db
from app.config.redis_config import get_redis_client
from app.modules.staff_operations.repository import StaffOperationsRepository
from app.modules.staff_operations.service import StaffOperationsService
from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.booking.services.payment_service import PaymentService
from app.modules.booking.dependencies import get_payment_service
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.folio.repository import FolioRepository
from app.Images.image_services import ImageService


def get_staff_operations_service(
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis_client),
    payment_service: PaymentService = Depends(get_payment_service),
) -> StaffOperationsService:
    staff_ops_repo = StaffOperationsRepository(db)
    booking_repo = BookingRepository(db)
    room_repo = RoomRepository(db)
    property_repo = PropertyRepository(db)
    offer_repo = SpecialOfferRepository(db)
    discount_code_repo = DiscountCodeRepository(db)
    folio_repo = FolioRepository(db)
    image_service = ImageService()
    return StaffOperationsService(
        db=db,
        staff_ops_repo=staff_ops_repo,
        booking_repo=booking_repo,
        room_repo=room_repo,
        property_repo=property_repo,
        offer_repo=offer_repo,
        discount_code_repo=discount_code_repo,
        redis_client=redis_client,
        folio_repo=folio_repo,
        image_service=image_service,
        payment_service=payment_service,
    )
