from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.booking.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.booking.payment.factory import PaymentServiceFactory
from app.modules.booking.services.payment_service import PaymentService
from app.modules.booking.services.booking_service import BookingService

from fastapi import Depends
from app.config.database_config import get_db
from app.config.redis_config import get_redis_client
from app.config.settings_config import settings


def get_payment_service_factory() -> PaymentServiceFactory:
    return PaymentServiceFactory(
        stripe_api_key=settings.STRIPE_SECRET_KEY,
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        razorpay_key_secret=settings.RAZORPAY_KEY_SECRET,
    )


def get_payment_service(
    factory: PaymentServiceFactory = Depends(get_payment_service_factory),
) -> PaymentService:
    return PaymentService(factory)


def get_booking_service(
    db: AsyncSession = Depends(get_db),
    redis_cli: AsyncRedis = Depends(get_redis_client),
    payment_service: PaymentService = Depends(get_payment_service),
) -> BookingService:
    booking_repo = BookingRepository(db)
    room_repo = RoomRepository(db)
    property_repo = PropertyRepository(db)
    idempotency_repo = IdempotencyRepository(redis_cli)
    offer_repo = SpecialOfferRepository(db)
    discount_code_repo = DiscountCodeRepository(db)
    return BookingService(
        db=db,
        booking_repo=booking_repo,
        room_repo=room_repo,
        property_repo=property_repo,
        idempotency_repo=idempotency_repo,
        payment_service=payment_service,
        redis_client=redis_cli,
        offer_repo=offer_repo,
        discount_code_repo=discount_code_repo,
    )
