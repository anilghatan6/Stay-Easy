import asyncio

from app.config.database_config import AsyncSessionLocal
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


async def _expire_stale_bookings_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            async with AsyncSessionLocal() as db:
                from app.modules.booking.repositories.booking_repository import BookingRepository
                from app.modules.booking.repositories.idempotency_repository import IdempotencyRepository
                from app.modules.pms.repositories.room_repo import RoomRepository
                from app.modules.pms.repositories.properties_repo import PropertyRepository
                from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
                from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
                from app.modules.booking.services.payment_service import PaymentService
                from app.modules.booking.payment.factory import PaymentServiceFactory
                from app.modules.booking.services.booking_service import BookingService
                from app.config.redis_config import redis_pool
                import redis.asyncio as aioredis

                redis_client = aioredis.Redis(connection_pool=redis_pool)
                try:
                    booking_repo = BookingRepository(db)
                    room_repo = RoomRepository(db)
                    property_repo = PropertyRepository(db)
                    idempotency_repo = IdempotencyRepository(redis_client)
                    offer_repo = SpecialOfferRepository(db)
                    discount_code_repo = DiscountCodeRepository(db)
                    factory = PaymentServiceFactory("", "", "")
                    payment_service = PaymentService(factory)

                    service = BookingService(
                        db, booking_repo, room_repo, property_repo,
                        idempotency_repo, payment_service, redis_client,
                        offer_repo, discount_code_repo,
                    )
                    expired = await service.expire_stale_bookings()
                    if expired > 0:
                        logger.info(f"[ExpiryLoop] Expired {expired} stale booking(s)")
                finally:
                    await redis_client.close()
        except Exception as e:
            logger.error(f"[ExpiryLoop] Error expiring stale bookings: {e}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass