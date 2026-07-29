import uuid
import math
import secrets
import asyncio
import os
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.booking.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository

from app.modules.booking.services.payment_service import PaymentService

from app.utils.exceptions import (
    InvalidDateException,
    RoomsUnavailableError,
    ServiceException,
    RedisException,
    RepositoryException,
    BookingException,
    UnsupportedGatewayError,
    PaymentGatewayError,
    ServiceBusyError,
)
from app.modules.booking.models.booking_model import PaymentGateway as PGEnum

from app.utils.logging import LoggerFactory

load_dotenv()

logger = LoggerFactory.get_logger(__name__)
SOFT_LOCK_TTL_SECONDS = int(os.getenv("SOFT_LOCK_TTL_SECONDS"))


class BookingService:
    def __init__(
        self,
        db: AsyncSession,
        booking_repo: BookingRepository,
        room_repo: RoomRepository,
        property_repo: PropertyRepository,
        idempotency_repo: IdempotencyRepository,
        payment_service: PaymentService,
        redis_client,
        offer_repo: SpecialOfferRepository,
        discount_code_repo: DiscountCodeRepository,
    ):
        self.booking_repo = booking_repo
        self.room_repo = room_repo
        self.property_repo = property_repo
        self.idempotency_repo = idempotency_repo
        self.redis = redis_client
        self.payment_service = payment_service
        self.db = db
        self.offer_repo = offer_repo
        self.discount_code_repo = discount_code_repo

    def _generate_ref_number(self) -> str:
        return f"BK-{secrets.token_hex(4).upper()}"

    async def create_booking(
        self,
        idempotency_key: str,
        guest_id: uuid.UUID,
        property_id: uuid.UUID,
        room_ids: list[uuid.UUID],
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
    ) -> dict:

        try:
            reserved = await self.idempotency_repo.try_reserve(idempotency_key)

            if not reserved:
                for _ in range(10):
                    result = await self.idempotency_repo.get_result(idempotency_key)
                    if result is not None:
                        return result
                    await asyncio.sleep(0.1)
                raise ServiceBusyError(
                    "Original request is still processing, please retry shortly"
                )

            nights = (check_out - check_in).days
            if nights <= 0:
                await self.idempotency_repo.release(idempotency_key)
                raise InvalidDateException("check out must be after check in")

            if not room_ids:
                raise RoomsUnavailableError("No rooms selected for booking")

            rooms_needed = len(room_ids)

            # Fetch the exact rooms the guest picked
            requested_rooms = await self.room_repo.get_by_ids_with_details(room_ids)

            if len(requested_rooms) != rooms_needed:
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError("Some rooms are invalid or unavailable")

            # Confirm every requested room belongs to the stated property
            if any(r.property_id != property_id for r in requested_rooms):
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "Some rooms do not belong to the selected property"
                )

            # Capacity sanity-check: even split across rooms
            adults_per_room = math.ceil(adults / rooms_needed)
            children_per_room = math.ceil(children / rooms_needed)

            undersized = [
                r
                for r in requested_rooms
                if r.max_adults < adults_per_room or r.max_children < children_per_room
            ]

            if undersized:
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "One or more selected rooms cannot accommodate the requested guests"
                )

            # step 2:soft lock (within-property concurrency). Lock exactly these rooms and re-verify availability now
            still_free_ids = await self.room_repo.lock_and_check_rooms(
                room_ids, check_in, check_out
            )

            if len(still_free_ids) < rooms_needed:
                await self.db.rollback()
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "One or more rooms were just booked by another guest. Please choose different rooms or dates."
                )

            nights = (check_out - check_in).days
            subtotal = Decimal(str(sum(r.base_rate for r in requested_rooms) * nights))

            active_offers = await self.offer_repo.get_active_offers(
                property_id, check_in, check_out
            )
            special_offer_discount = Decimal(0)
            remaining = subtotal
            for offer in active_offers:
                offer_discount = (
                    remaining * Decimal(str(offer.discount_percentage)) / Decimal(100)
                )
                offer_discount = min(offer_discount, remaining)
                special_offer_discount += offer_discount
                remaining -= offer_discount
            special_offer_discount = special_offer_discount.quantize(Decimal("0.01"))
            total_amount = subtotal - special_offer_discount

            booking = await self.booking_repo.create_booking(
                guest_id=guest_id,
                property_id=property_id,
                room_ids=room_ids,
                check_in=check_in,
                check_out=check_out,
                total_amount=total_amount,
                subtotal=subtotal,
                special_offer_discount=special_offer_discount,
                ref_number=self._generate_ref_number(),
            )

            await self.db.commit()

            property_obj = await self.property_repo.get_by_id(property_id)

            soft_lock_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=SOFT_LOCK_TTL_SECONDS
            )

            await self.redis.set(
                f"booking:softlock:{booking.id}", "pending", ex=SOFT_LOCK_TTL_SECONDS
            )

            nights = (check_out - check_in).days
            rooms_data = []
            for r in requested_rooms:
                room_subtotal = float(r.base_rate) * nights
                rooms_data.append(
                    {
                        "room_id": r.id,
                        "room_name": r.room_name,
                        "room_type": r.room_type.room_type_name if r.room_type else "",
                        "bed_type": r.bed_type.bed_name if r.bed_type else "",
                        "max_adults": r.max_adults,
                        "max_children": r.max_children,
                        "base_rate": float(r.base_rate),
                        "nights": nights,
                        "subtotal": room_subtotal,
                    }
                )

            response = {
                "booking_id": booking.id,
                "ref_number": booking.ref_number,
                "status": booking.status.value
                if hasattr(booking.status, "value")
                else booking.status,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "payment_gateway": None,
                "property": {
                    "id": property_obj.id,
                    "name": property_obj.name,
                    "type": property_obj.type.value
                    if hasattr(property_obj.type, "value")
                    else str(property_obj.type),
                    "city": property_obj.city,
                    "country": property_obj.country,
                    "currency": property_obj.currency or "USD",
                }
                if property_obj
                else None,
                "rooms": rooms_data,
                "total_amount": float(booking.total_amount),
                "subtotal": float(booking.subtotal),
                "special_offer_discount": float(booking.special_offer_discount),
                "coupon_code": booking.coupon_code,
                "coupon_discount": float(booking.coupon_discount),
                "soft_lock_expires_at": soft_lock_expires_at,
            }

            await self.idempotency_repo.save_result(idempotency_key, response)
            return response

        except (
            RoomsUnavailableError,
            InvalidDateException,
            ServiceException,
            RedisException,
            RepositoryException,
            ServiceBusyError,
        ):
            raise
        except Exception as e:
            await self.db.rollback()
            await self.idempotency_repo.release(idempotency_key)
            logger.error(f"[BookingService] Unexpected error creating booking: {e}")
            raise ServiceException("Could not create booking. Please try again.")

    async def confirm_payment(
        self,
        idempotency_key: str,
        ref_number: str,
        gateway_payload: dict,
    ) -> dict:
        reserved = await self.idempotency_repo.try_reserve(idempotency_key)

        if not reserved:
            for _ in range(10):
                result = await self.idempotency_repo.get_result(idempotency_key)
                if result is not None:
                    return result
                await asyncio.sleep(0.1)
            raise ServiceBusyError(
                "Original request is still processing, please retry shortly"
            )

        try:
            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None:
                response = {"status": "NOT_FOUND", "message": "Booking not found"}
                await self.idempotency_repo.save_result(idempotency_key, response)
                return response

            if booking.status == "EXPIRED":
                response = {
                    "status": "EXPIRED",
                    "message": "This booking's hold has already expired.",
                }
                await self.idempotency_repo.save_result(idempotency_key, response)
                return response

            if booking.status == "CONFIRMED":
                response = {
                    "status": "CONFIRMED",
                    "message": "Booking already confirmed",
                }
                await self.idempotency_repo.save_result(idempotency_key, response)
                return response

            # Verify with the gateway BEFORE touching status
            payment_verified = await self.payment_service.verify(
                booking.payment_gateway, ref_number, gateway_payload
            )

            if not payment_verified:
                await self.idempotency_repo.release(idempotency_key)
                return {
                    "status": "PAYMENT_NOT_VERIFIED",
                    "message": "Payment could not be verified. Booking not confirmed.",
                }  # deliberately not cached — allow retry once payment actually clears

            confirmed = await self.booking_repo.try_confirm_booking(ref_number)

            if not confirmed:
                # Lost the race to the expiry job
                await self.db.commit()
                await self.payment_service.refund(
                    booking.payment_gateway, ref_number, gateway_payload
                )
                response = {
                    "status": "EXPIRED_REFUNDED",
                    "message": "Your hold expired before payment completed. You have been refunded.",
                }
                await self.idempotency_repo.save_result(idempotency_key, response)
                return response

            await self.db.commit()
            await self.redis.delete(f"booking:softlock:{booking.id}")

            response = {
                "status": "CONFIRMED",
                "message": "Booking confirmed successfully",
                "booking_id": str(booking.id),
                "ref_number": booking.ref_number,
            }
            await self.idempotency_repo.save_result(idempotency_key, response)
            return response

        except (RedisException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            await self.idempotency_repo.release(idempotency_key)
            logger.error(
                f"[BookingService] Unexpected error confirming payment for {ref_number}: {e}"
            )
            raise ServiceException("Could not confirm payment. Please try again.")

    async def create_payment_intent(
        self,
        ref_number: str,
        payment_gateway: str,
    ) -> dict:
        try:
            try:
                PGEnum(payment_gateway.upper())
            except ValueError:
                raise UnsupportedGatewayError(
                    internal_detail=f"Unsupported payment gateway: {payment_gateway}"
                )

            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None:
                raise BookingException("Booking not found")

            if booking.status == "EXPIRED":
                raise BookingException(
                    "This booking has expired. Please search and reserve again."
                )

            if booking.status == "CONFIRMED":
                raise BookingException("This booking has already been paid for.")

            if booking.status != "PENDING":
                raise BookingException(
                    f"Booking is in status {booking.status}, cannot proceed to payment"
                )

            updated_booking = await self.booking_repo.set_payment_gateway(
                ref_number, payment_gateway
            )
            await self.db.commit()

            if updated_booking is None:
                raise BookingException("Booking not found")

            property_obj = await self.property_repo.get_by_id(
                updated_booking.property_id
            )
            currency = property_obj.currency if property_obj else "USD"

            intent_data = await self.payment_service.create_intent(
                gateway=payment_gateway,
                ref_number=ref_number,
                amount=updated_booking.total_amount,
                currency=currency,
            )

            return {
                "ref_number": ref_number,
                "payment_gateway": payment_gateway,
                "amount": float(updated_booking.total_amount),
                "currency": currency,
                **intent_data,
            }

        except (
            UnsupportedGatewayError,
            PaymentGatewayError,
            ServiceException,
            BookingException,
        ):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Unexpected error creating payment intent for {ref_number}: {e}"
            )
            raise ServiceException("Could not create payment intent. Please try again.")

    async def get_booking_detail(
        self, ref_number: str, guest_id: uuid.UUID
    ) -> dict | None:
        logger.info(f"[BookingService] Getting booking details for {ref_number}")

        try:
            booking = await self.booking_repo.get_by_ref_with_rooms(ref_number)
            if booking is None or booking.guest_id != guest_id:
                logger.info(f"Booking not found or guest does not match: {ref_number}")
                return None

            property_obj = await self.property_repo.get_by_id(booking.property_id)
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            rooms = await self.room_repo.get_by_ids_with_details(room_ids)
            rooms_map = {r.id: r for r in rooms}
            nights = (booking.checkout_date - booking.checkin_date).days
            rooms_data = []
            for br in booking.booking_rooms:
                r = rooms_map.get(br.room_unit_id)
                if r:
                    room_subtotal = float(r.base_rate) * nights
                    rooms_data.append(
                        {
                            "room_id": r.id,
                            "room_name": r.room_name,
                            "room_type": r.room_type.room_type_name
                            if r.room_type
                            else "",
                            "bed_type": r.bed_type.bed_name if r.bed_type else "",
                            "max_adults": r.max_adults,
                            "max_children": r.max_children,
                            "base_rate": float(r.base_rate),
                            "nights": nights,
                            "subtotal": room_subtotal,
                        }
                    )
            soft_lock_key = f"booking:softlock:{booking.id}"
            remaining_ttl = await self.redis.ttl(soft_lock_key)
            if remaining_ttl > 0:
                soft_lock_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=remaining_ttl
                )
            else:
                soft_lock_expires_at = datetime.now(timezone.utc)

            return {
                "booking_id": booking.id,
                "ref_number": booking.ref_number,
                "status": booking.status.value
                if hasattr(booking.status, "value")
                else booking.status,
                "check_in": booking.checkin_date,
                "check_out": booking.checkout_date,
                "nights": nights,
                "payment_gateway": booking.payment_gateway.value
                if hasattr(booking.payment_gateway, "value")
                else booking.payment_gateway,
                "property": {
                    "id": property_obj.id,
                    "name": property_obj.name,
                    "type": property_obj.type.value
                    if hasattr(property_obj.type, "value")
                    else str(property_obj.type),
                    "city": property_obj.city,
                    "country": property_obj.country,
                    "currency": property_obj.currency or "USD",
                }
                if property_obj
                else None,
                "rooms": rooms_data,
                "total_amount": float(booking.total_amount),
                "subtotal": float(booking.subtotal),
                "special_offer_discount": float(booking.special_offer_discount),
                "coupon_code": booking.coupon_code,
                "coupon_discount": float(booking.coupon_discount),
                "soft_lock_expires_at": soft_lock_expires_at,
            }
        except RepositoryException:
            raise

        except Exception as e:
            logger.error(
                f"[BookingService] Error getting booking details for {ref_number}: {e}"
            )
            raise ServiceException("Could not get booking details. Please try again.")

    async def get_guest_bookings(
        self, guest_id: uuid.UUID, skip: int, limit: int, page: int = 1
    ) -> dict:
        logger.info("getting guest bookings")
        try:
            bookings, total = await self.booking_repo.get_bookings_by_guest(
                guest_id, skip, limit
            )
            return {
                "bookings": bookings,
                "total": total,
            }
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(f"[BookingService] Error getting guest bookings: {e}")
            raise ServiceException("Could not get guest bookings. Please try again.")

    async def apply_discount_code(
        self, ref_number: str, guest_id: uuid.UUID, coupon_code: str
    ) -> dict:
        logger.info(f"apply_discount_code to booking {ref_number} by guest {guest_id}")
        try:
            booking = await self.booking_repo.get_by_ref_with_rooms(ref_number)
            if booking is None or booking.guest_id != guest_id:
                raise BookingException("Booking not found")
            if booking.status != "PENDING":
                raise BookingException(
                    f"Cannot apply discount to a booking with status {booking.status}"
                )

            discount_code = await self.discount_code_repo.get_valid_code(
                booking.property_id, coupon_code
            )
            if discount_code is None:
                raise BookingException("Invalid or expired discount code")

            if booking.subtotal < discount_code.min_amount:
                raise BookingException(
                    f"Minimum order amount of {discount_code.min_amount} not met"
                )

            total_after_offers = booking.subtotal - booking.special_offer_discount

            if discount_code.type.value == "PERCENTAGE":
                coupon_discount = (
                    total_after_offers
                    * Decimal(str(discount_code.discount_value))
                    / Decimal(100)
                )
            else:
                coupon_discount = Decimal(str(discount_code.discount_value))
            coupon_discount = min(coupon_discount, total_after_offers)
            coupon_discount = coupon_discount.quantize(Decimal("0.01"))

            await self.discount_code_repo.increment_used_count(discount_code.id)

            updated = await self.booking_repo.apply_coupon(
                ref_number, coupon_code, coupon_discount
            )
            if updated is None:
                await self.discount_code_repo.decrement_used_count(discount_code.id)
                raise BookingException("Booking not found")

            await self.db.commit()

            property_obj = await self.property_repo.get_by_id(booking.property_id)
            nights = (booking.checkout_date - booking.checkin_date).days
            rooms_data = []
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            rooms = await self.room_repo.get_by_ids_with_details(room_ids)
            rooms_map = {r.id: r for r in rooms}
            for br in booking.booking_rooms:
                r = rooms_map.get(br.room_unit_id)
                if r:
                    room_subtotal = float(r.base_rate) * nights
                    rooms_data.append(
                        {
                            "room_id": r.id,
                            "room_name": r.room_name,
                            "room_type": r.room_type.room_type_name
                            if r.room_type
                            else "",
                            "bed_type": r.bed_type.bed_name if r.bed_type else "",
                            "max_adults": r.max_adults,
                            "max_children": r.max_children,
                            "base_rate": float(r.base_rate),
                            "nights": nights,
                            "subtotal": room_subtotal,
                        }
                    )

            soft_lock_key = f"booking:softlock:{updated.id}"
            remaining_ttl = await self.redis.ttl(soft_lock_key)
            if remaining_ttl > 0:
                soft_lock_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=remaining_ttl
                )
            else:
                soft_lock_expires_at = datetime.now(timezone.utc)

            return {
                "booking_id": updated.id,
                "ref_number": updated.ref_number,
                "status": updated.status.value
                if hasattr(updated.status, "value")
                else updated.status,
                "check_in": updated.checkin_date,
                "check_out": updated.checkout_date,
                "nights": nights,
                "payment_gateway": updated.payment_gateway.value
                if hasattr(updated.payment_gateway, "value")
                else updated.payment_gateway,
                "property": {
                    "id": property_obj.id,
                    "name": property_obj.name,
                    "type": property_obj.type.value
                    if hasattr(property_obj.type, "value")
                    else str(property_obj.type),
                    "city": property_obj.city,
                    "country": property_obj.country,
                    "currency": property_obj.currency or "USD",
                }
                if property_obj
                else None,
                "rooms": rooms_data,
                "total_amount": float(updated.total_amount),
                "subtotal": float(updated.subtotal),
                "special_offer_discount": float(updated.special_offer_discount),
                "coupon_code": updated.coupon_code,
                "coupon_discount": float(updated.coupon_discount),
                "soft_lock_expires_at": soft_lock_expires_at,
            }
        except (BookingException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error applying discount to {ref_number}: {e}"
            )
            raise ServiceException("Could not apply discount code.")

    async def remove_discount_code(self, ref_number: str, guest_id: uuid.UUID) -> dict:
        logger.info(
            f"remove_discount_code from booking {ref_number} by guest {guest_id}"
        )
        try:
            booking = await self.booking_repo.get_by_ref_with_rooms(ref_number)
            if booking is None or booking.guest_id != guest_id:
                raise BookingException("Booking not found")
            if booking.status != "PENDING":
                raise BookingException(
                    f"Cannot remove discount from a booking with status {booking.status}"
                )
            if booking.coupon_code is None:
                raise BookingException("No discount code applied to this booking")

            discount_code = await self.discount_code_repo.get_discount_code(
                booking.property_id, booking.coupon_code
            )
            if discount_code is not None:
                await self.discount_code_repo.decrement_used_count(discount_code.id)

            updated = await self.booking_repo.remove_coupon(ref_number)
            if updated is None:
                raise BookingException("Booking not found")

            await self.db.commit()

            property_obj = await self.property_repo.get_by_id(booking.property_id)
            nights = (booking.checkout_date - booking.checkin_date).days
            rooms_data = []
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            rooms = await self.room_repo.get_by_ids_with_details(room_ids)
            rooms_map = {r.id: r for r in rooms}
            for br in booking.booking_rooms:
                r = rooms_map.get(br.room_unit_id)
                if r:
                    room_subtotal = float(r.base_rate) * nights
                    rooms_data.append(
                        {
                            "room_id": r.id,
                            "room_name": r.room_name,
                            "room_type": r.room_type.room_type_name
                            if r.room_type
                            else "",
                            "bed_type": r.bed_type.bed_name if r.bed_type else "",
                            "max_adults": r.max_adults,
                            "max_children": r.max_children,
                            "base_rate": float(r.base_rate),
                            "nights": nights,
                            "subtotal": room_subtotal,
                        }
                    )

            return {
                "booking_id": updated.id,
                "ref_number": updated.ref_number,
                "status": updated.status.value
                if hasattr(updated.status, "value")
                else updated.status,
                "check_in": updated.checkin_date,
                "check_out": updated.checkout_date,
                "nights": nights,
                "payment_gateway": updated.payment_gateway.value
                if hasattr(updated.payment_gateway, "value")
                else updated.payment_gateway,
                "property": {
                    "id": property_obj.id,
                    "name": property_obj.name,
                    "type": property_obj.type.value
                    if hasattr(property_obj.type, "value")
                    else str(property_obj.type),
                    "city": property_obj.city,
                    "country": property_obj.country,
                    "currency": property_obj.currency or "USD",
                }
                if property_obj
                else None,
                "rooms": rooms_data,
                "total_amount": float(updated.total_amount),
                "subtotal": float(updated.subtotal),
                "special_offer_discount": float(updated.special_offer_discount),
                "coupon_code": updated.coupon_code,
                "coupon_discount": float(updated.coupon_discount),
            }
        except (BookingException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error removing discount from {ref_number}: {e}"
            )
            raise ServiceException("Could not remove discount code.")

    async def delete_stale_bookings(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=SOFT_LOCK_TTL_SECONDS)

        try:
            stale_bookings = await self.booking_repo.get_pending_older_than(cutoff)

            count = 0
            for booking in stale_bookings:
                expired = await self.booking_repo.try_delete_pending_booking(booking.id)
                if expired:
                    count += 1
                    await self.redis.delete(f"booking:softlock:{booking.id}")

            await self.db.commit()
            logger.info(f"[BookingService] deleted {count} stale bookings")
            return count

        except Exception as e:
            await self.db.rollback()
            logger.error(f"[BookingService] Failed to delete stale bookings: {e}")
            raise ServiceException("Could not process booking expiry.")
