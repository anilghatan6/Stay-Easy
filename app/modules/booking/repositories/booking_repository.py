import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func, select, delete
from sqlalchemy.orm import selectinload,joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.models.booking_model import (
    Booking,
    BookingRoom,
    MasterBookingStatus,
    PaymentGateway as PGEnum,
)
from app.utils.exceptions import RepositoryException, UnsupportedGatewayError

from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_booking(
        self,
        guest_id: uuid.UUID,
        property_id: uuid.UUID,
        room_ids: list[uuid.UUID],
        adults: int,
        children: int,
        check_in: date,
        check_out: date,
        total_amount: Decimal,
        subtotal: Decimal,
        special_offer_discount: Decimal,
        ref_number: str,
    ) -> Booking:
        logger.info("[BookingRepository] Creating booking")
        try:
            booking = Booking(
                id=uuid.uuid4(),
                property_id=property_id,
                guest_id=guest_id,
                status=MasterBookingStatus.PENDING,
                number_of_adults=adults,
                number_of_children=children,
                checkin_date=check_in,
                checkout_date=check_out,
                total_amount=total_amount,
                subtotal=subtotal,
                special_offer_discount=special_offer_discount,
                ref_number=ref_number,
            )
            self.db.add(booking)
            await self.db.flush()

            for room_id in room_ids:
                self.db.add(
                    BookingRoom(
                        id=uuid.uuid4(),
                        booking_id=booking.id,
                        room_unit_id=room_id,
                    )
                )
            logger.info("[BookingRepository] Booking created successfully")
            return booking

        except SQLAlchemyError as e:
            logger.error(f"[BookingRepository] Failed to create booking: {e}")
            raise RepositoryException(
                "Could not create booking. Please try again."
            ) from e
 
    async def get_by_ref(self, ref_number: str) -> Booking | None:
        logger.info("[BookingRepository] Fetching booking by ref")
        try:
            stmt = select(Booking).where(Booking.ref_number == ref_number)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to fetch booking by ref {ref_number}: {e}"
            )
            raise RepositoryException(
                "Could not fetch booking details. Please try again."
            ) from e

    async def try_confirm_booking(self, ref_number: str) -> bool:
        """
        Attempts to mark a booking CONFIRMED. Returns False if it's already
        EXPIRED (payment succeeded too late) — the guard against the
        payment-vs-expiry race condition.
        """
        logger.info("[BookingRepository] Confirming booking")
        try:
            result = await self.db.execute(
                select(Booking)
                .where(Booking.ref_number == ref_number)
                .with_for_update()
            )
            booking = result.scalar_one_or_none()

            if booking is None or booking.status == MasterBookingStatus.EXPIRED:
                return False

            booking.status = MasterBookingStatus.CONFIRMED
            return True

        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to confirm booking {ref_number}: {e}"
            )
            raise RepositoryException(
                "Could not confirm booking. Please try again."
            ) from e

    async def try_delete_pending_booking(self, booking_id: uuid.UUID) -> bool:
        """
        Attempts to hard delete a PENDING booking. Returns False if it's
        no longer PENDING (already confirmed or processed by a parallel task).
        """
        logger.info(f"[BookingRepository] Attempting clean deletion of booking {booking_id}")
        try:
            # 1. Fetch with row-level locking to prevent a race condition 
            # (e.g., user pays at the exact millisecond the deletion task wakes up)
            result = await self.db.execute(
                select(Booking).where(Booking.id == booking_id).with_for_update()
            )
            booking = result.scalar_one_or_none()

            # Guard clause: Allow deletion if it's PENDING or EXPIRED
            valid_statuses_for_deletion = (MasterBookingStatus.PENDING, MasterBookingStatus.EXPIRED)
            if booking is None or booking.status not in valid_statuses_for_deletion:
                return False

            # 2. Execute the clear deletion
            await self.db.execute(
                delete(Booking).where(Booking.id == booking_id)
            )
            return True

        except SQLAlchemyError as e:
            logger.error(f"[BookingRepository] Failed to delete booking {booking_id}: {e}")
            raise RepositoryException("Could not delete booking.")

    async def get_pending_older_than(self, cutoff: datetime) -> list[Booking]:
        logger.info("[BookingRepository] getting pending older bookings")
        try:
            stmt = select(Booking).where(
                # Booking.status == MasterBookingStatus.PENDING,
                Booking.status.in_([MasterBookingStatus.PENDING, MasterBookingStatus.EXPIRED]),
                Booking.created_at < cutoff,
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to fetch stale pending bookings: {e}"
            )
            raise RepositoryException("Could not fetch pending bookings.")

    async def get_by_ref_with_rooms(self, ref_number: str) -> Booking | None:
        logger.info("[BookingRepository] Fetching booking with rooms by ref")
        try:
            stmt = (
                select(Booking)
                .where(Booking.ref_number == ref_number)
                .options(selectinload(Booking.booking_rooms))
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to fetch booking with rooms {ref_number}: {e}"
            )
            raise RepositoryException(
                "Could not fetch booking details. Please try again."
            ) 

    async def get_bookings_by_guest(
        self, guest_id: uuid.UUID, skip: int, limit: int
    ) -> tuple[list[Booking], int]:
        logger.info("[BookingRepository] Fetching bookings by guest")
        try:
            excluded_statuses = [
                MasterBookingStatus.CANCELLED,
                MasterBookingStatus.EXPIRED,
            ]

            stmt = (
                select(Booking)
                .options(joinedload(Booking.property))
                .where(
                    Booking.guest_id == guest_id, 
                    ~Booking.status.in_(excluded_statuses)
                )
                .order_by(Booking.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)

            total_stmt = (
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.guest_id == guest_id,
                    ~Booking.status.in_(excluded_statuses)
                )
            )

            total_result = await self.db.execute(total_stmt)

            total = total_result.scalar() or 0
            bookings = result.scalars().all()
            return bookings, total
        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to fetch bookings for guest {guest_id}: {e}"
            )
            raise RepositoryException(
                "Could not fetch bookings. Please try again."
            ) 

    async def count_by_guest(self, guest_id: uuid.UUID) -> int:
        logger.info("[BookingRepository] Counting bookings by guest")
        try:
            excluded_statuses = [
                MasterBookingStatus.CANCELLED,
                MasterBookingStatus.EXPIRED,
            ]
            stmt = (
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.guest_id == guest_id, ~Booking.status.in_(excluded_statuses)
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one()
        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to count bookings for guest {guest_id}: {e}"
            )
            raise RepositoryException(
                "Could not count bookings. Please try again."
            ) 

    async def set_payment_gateway(self, ref_number: str, payment_gateway: str):
        try:
            try:
                pg = PGEnum(payment_gateway.upper())
            except ValueError:
                raise UnsupportedGatewayError(
                    internal_detail=f"Unsupported payment gateway: {payment_gateway}"
                )

            result = await self.db.execute(
                select(Booking)
                .where(Booking.ref_number == ref_number)
                .with_for_update()
            )
            booking = result.scalar_one_or_none()

            if booking is None:
                return None

            booking.payment_gateway = pg
            return booking

        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to set payment gateway for {ref_number}: {e}"
            )
            raise RepositoryException("Could not update booking payment method.") 

    async def apply_coupon(
        self, ref_number: str, coupon_code: str, coupon_discount: Decimal
    ) -> Booking | None:
        logger.info(
            f"[BookingRepository] Applying coupon {coupon_code} to {ref_number}"
        )
        try:
            result = await self.db.execute(
                select(Booking)
                .where(Booking.ref_number == ref_number)
                .with_for_update()
            )
            booking = result.scalar_one_or_none()
            if booking is None:
                return None
            booking.coupon_code = coupon_code.strip().upper()
            booking.coupon_discount = coupon_discount
            booking.total_amount = (
                booking.subtotal - booking.special_offer_discount - coupon_discount
            )
            return booking
        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to apply coupon to {ref_number}: {e}"
            )
            raise RepositoryException("Could not apply discount code.") 

    async def remove_coupon(self, ref_number: str) -> Booking | None:
        logger.info(f"[BookingRepository] Removing coupon from {ref_number}")
        try:
            result = await self.db.execute(
                select(Booking)
                .where(Booking.ref_number == ref_number)
                .with_for_update()
            )
            booking = result.scalar_one_or_none()
            if booking is None:
                return None
            booking.coupon_code = None
            booking.coupon_discount = Decimal(0)
            booking.total_amount = booking.subtotal - booking.special_offer_discount
            return booking
        except SQLAlchemyError as e:
            logger.error(
                f"[BookingRepository] Failed to remove coupon from {ref_number}: {e}"
            )
            raise RepositoryException("Could not remove discount code.") 
