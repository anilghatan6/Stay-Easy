import asyncio
import math
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import AsyncSessionLocal
from app.config.settings_config import settings
from app.modules.booking.models.booking_model import PaymentGateway as PGEnum
from app.modules.booking.models.booking_model import (
    MasterBookingStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.booking.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from app.modules.booking.services.payment_service import PaymentService
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.utils.exceptions import (
    BookingException,
    InvalidDateException,
    InvalidReturnUrl,
    PaymentGatewayError,
    RedisException,
    RepositoryException,
    RoomsUnavailableError,
    ServiceBusyError,
    ServiceException,
    UnsupportedGatewayError,
    UrlValidationException,
)
from app.utils.logging import LoggerFactory
from app.utils.mail_services import (
    send_booking_confirmed_guest_email,
    send_booking_confirmed_owner_email,
)
from app.utils.url_validation import validate_khalti_return_url

logger = LoggerFactory.get_logger(__name__)
SOFT_LOCK_TTL_SECONDS = settings.SOFT_LOCK_TTL_SECONDS


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

    # ─────────────────────────── private helpers ─────────────────────────────

    def _generate_ref_number(self) -> str:
        return f"BK-{secrets.token_hex(4).upper()}"

    async def _wait_for_idempotent_result(self, key: str) -> dict:
        """Poll up to 1 second for a concurrent duplicate request to finish."""
        for _ in range(10):
            result = await self.idempotency_repo.get_result(key)
            if result is not None:
                return result
            await asyncio.sleep(0.1)
        raise ServiceBusyError(
            "Original request is still processing, please retry shortly"
        )

    def _build_property_dict(self, property_obj) -> dict | None:
        if not property_obj:
            return None
        return {
            "id": property_obj.id,
            "name": property_obj.name,
            "type": (
                property_obj.type.value
                if hasattr(property_obj.type, "value")
                else str(property_obj.type)
            ),
            "city": property_obj.city,
            "country": property_obj.country,
            "currency": property_obj.currency or "USD",
            "photo": property_obj.photos.get("cover") if property_obj.photos else None,
            "phone_number": property_obj.phone_number,
            "email": property_obj.email,
        }

    def _build_rooms_data(self, rooms: list, nights: int) -> list:
        return [
            {
                "room_id": r.id,
                "room_name": r.room_name,
                "room_type": r.room_type.room_type_name if r.room_type else "",
                "bed_type": r.bed_type.bed_name if r.bed_type else "",
                "max_adults": r.max_adults,
                "max_children": r.max_children,
                "base_rate": float(r.base_rate),
                "nights": nights,
                "subtotal": float(r.base_rate) * nights,
                "photo": r.photos.get("cover") if r.photos else None,
                "cancellation_title": r.cancellation_title,
                "cancellation_description": r.cancellation_description,
            }
            for r in rooms
        ]

    async def _get_soft_lock_expiry(self, booking_id) -> datetime:
        """Returns the UTC datetime when the soft lock expires (or now if already gone)."""
        remaining_ttl = await self.redis.ttl(f"booking:softlock:{booking_id}")
        if remaining_ttl > 0:
            return datetime.now(timezone.utc) + timedelta(seconds=remaining_ttl)
        return datetime.now(timezone.utc)

    async def _fetch_rooms_for_booking(self, booking) -> list:
        """Fetch fully-detailed room objects, ordered by booking_rooms relation."""
        room_ids = [br.room_unit_id for br in booking.booking_rooms]
        rooms = await self.room_repo.get_by_ids_with_details(room_ids)
        rooms_map = {r.id: r for r in rooms}
        return [
            rooms_map[br.room_unit_id]
            for br in booking.booking_rooms
            if br.room_unit_id in rooms_map
        ]

    def _build_full_booking_response(
        self,
        booking,
        property_obj,
        rooms_data: list,
        nights: int,
        soft_lock_expires_at: datetime | None,
        number_of_adults: int | None = None,
        number_of_children: int | None = None,
        special_offer_applied: list | None = None,
    ) -> dict:
        """Assembles the standard booking detail response dict."""
        status = (
            booking.status.value if hasattr(booking.status, "value") else booking.status
        )
        payment_gateway = (
            booking.payment_gateway.value
            if hasattr(booking.payment_gateway, "value")
            else booking.payment_gateway
        )
        payment_method = (
            booking.payment_method.value
            if hasattr(booking.payment_method, "value")
            else booking.payment_method
        )
        payment_status = (
            booking.payment_status.value
            if hasattr(booking.payment_status, "value")
            else booking.payment_status
        )

        # Calculate advance hints from property settings
        min_advance_percentage = None
        max_advance_percentage = None
        min_advance_amount = None
        max_advance_amount = None

        if property_obj:
            min_pct = getattr(property_obj, "min_advance_percentage", None) or 10
            max_pct = getattr(property_obj, "max_advance_percentage", None) or 50
            min_advance_percentage = min_pct
            max_advance_percentage = max_pct
            min_advance_amount = float(booking.total_amount * Decimal(min_pct) / Decimal(100))
            max_advance_amount = float(booking.total_amount * Decimal(max_pct) / Decimal(100))

        return {
            "booking_id": booking.id,
            "ref_number": booking.ref_number,
            "status": status,
            "number_of_adults": (
                number_of_adults
                if number_of_adults is not None
                else booking.number_of_adults
            ),
            "number_of_children": (
                number_of_children
                if number_of_children is not None
                else booking.number_of_children
            ),
            "check_in": booking.checkin_date,
            "check_out": booking.checkout_date,
            "nights": nights,
            "payment_gateway": payment_gateway,
            "payment_method": payment_method,
            "payment_status": payment_status,
            "amount_paid": float(booking.amount_paid),
            "amount_due": float(booking.amount_due),
            "advance_amount": (
                float(booking.advance_amount)
                if booking.advance_amount is not None
                else None
            ),
            "min_advance_amount": min_advance_amount,
            "max_advance_amount": max_advance_amount,
            "min_advance_percentage": min_advance_percentage,
            "max_advance_percentage": max_advance_percentage,
            "property": self._build_property_dict(property_obj),
            "rooms": rooms_data,
            "total_amount": float(booking.total_amount),
            "subtotal": float(booking.subtotal),
            "special_offer_applied": special_offer_applied
            if special_offer_applied is not None
            else [],
            "special_offer_discount": float(booking.special_offer_discount),
            "coupon_code": booking.coupon_code,
            "coupon_discount": float(booking.coupon_discount),
            "soft_lock_expires_at": soft_lock_expires_at,
            "created_at": booking.created_at,
            "special_requests": booking.special_requests,
        }

    # ─────────────────────────── public methods ──────────────────────────────

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
                return await self._wait_for_idempotent_result(idempotency_key)

            nights = (check_out - check_in).days
            if nights <= 0:
                await self.idempotency_repo.release(idempotency_key)
                raise InvalidDateException("check out must be after check in")

            if not room_ids:
                raise RoomsUnavailableError("No rooms selected for booking")

            rooms_needed = len(room_ids)
            requested_rooms = await self.room_repo.get_by_ids_with_details(room_ids)

            if len(requested_rooms) != rooms_needed:
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError("Some rooms are invalid or unavailable")

            if any(r.property_id != property_id for r in requested_rooms):
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "Some rooms do not belong to the selected property"
                )

            # Capacity check: even split across rooms
            total_max_adults = sum(r.max_adults for r in requested_rooms)
            total_max_children = sum(r.max_children for r in requested_rooms)

            if adults > total_max_adults or children > total_max_children:
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "The selected room(s) cannot accommodate the total number of guests"
                )

            # Soft lock + re-verify availability
            still_free_ids = await self.room_repo.lock_and_check_rooms(
                room_ids, check_in, check_out
            )
            if len(still_free_ids) < rooms_needed:
                await self.db.rollback()
                await self.idempotency_repo.release(idempotency_key)
                raise RoomsUnavailableError(
                    "One or more rooms were just booked by another guest. "
                    "Please choose different rooms or dates."
                )

            # Pricing: subtotal → apply special offers → total
            subtotal = Decimal(str(sum(r.base_rate for r in requested_rooms) * nights))
            active_offers = await self.offer_repo.get_active_offers(
                property_id, check_in, check_out
            )

            special_offer_discount = Decimal(0)
            remaining = subtotal
            for offer in active_offers:
                offer_discount = min(
                    remaining * Decimal(str(offer.discount_percentage)) / Decimal(100),
                    remaining,
                )
                special_offer_discount += offer_discount
                remaining -= offer_discount
            special_offer_discount = special_offer_discount.quantize(Decimal("0.01"))

            special_offer_applied = [
                {"title": offer.title, "description": offer.description}
                for offer in active_offers
            ]

            booking = await self.booking_repo.create_booking(
                guest_id=guest_id,
                property_id=property_id,
                room_ids=room_ids,
                adults=adults,
                children=children,
                check_in=check_in,
                check_out=check_out,
                total_amount=subtotal - special_offer_discount,
                subtotal=subtotal,
                special_offer_discount=special_offer_discount,
                ref_number=self._generate_ref_number(),
            )
            await self.db.commit()

            # All bookings start as PENDING with soft-lock
            await self.redis.set(
                f"booking:softlock:{booking.id}", "pending", ex=SOFT_LOCK_TTL_SECONDS
            )
            soft_lock_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=SOFT_LOCK_TTL_SECONDS
            )

            property_obj = await self.property_repo.get_by_id(property_id)
            rooms_data = self._build_rooms_data(requested_rooms, nights)

            response = self._build_full_booking_response(
                booking=booking,
                property_obj=property_obj,
                rooms_data=rooms_data,
                nights=nights,
                soft_lock_expires_at=soft_lock_expires_at,
                number_of_adults=adults,
                number_of_children=children,
                special_offer_applied=special_offer_applied,
            )
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
        guest_id: uuid.UUID,
        background_tasks: BackgroundTasks,
    ) -> dict:
        reserved = await self.idempotency_repo.try_reserve(idempotency_key)
        if not reserved:
            return await self._wait_for_idempotent_result(idempotency_key)

        try:
            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None or booking.guest_id != guest_id:
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
                str(booking.payment_gateway), ref_number, gateway_payload
            )
            if not payment_verified:
                await self.idempotency_repo.release(idempotency_key)
                # Deliberately not cached — allow retry once payment actually clears
                return {
                    "status": "PAYMENT_NOT_VERIFIED",
                    "message": "Payment could not be verified. Booking not confirmed.",
                }

            # Determine payment status and amounts based on payment method
            if booking.payment_method == PaymentMethod.ADVANCE:
                paid_amount = booking.advance_amount or booking.total_amount
                remaining = booking.total_amount - paid_amount
                new_payment_status = PaymentStatus.PARTIAL
                new_amount_paid = paid_amount
                new_amount_due = remaining if remaining > Decimal("0") else Decimal("0.00")
            else:
                new_payment_status = PaymentStatus.PAID
                new_amount_paid = booking.total_amount
                new_amount_due = Decimal("0.00")

            confirmed = await self.booking_repo.try_confirm_booking(
                ref_number,
                payment_status=new_payment_status,
                amount_paid=new_amount_paid,
                amount_due=new_amount_due,
            )
            if not confirmed:
                # Lost the race to the expiry job
                await self.db.commit()
                await self.payment_service.refund(
                    str(booking.payment_gateway), ref_number, gateway_payload
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
            background_tasks.add_task(self.send_confirmation_emails, ref_number)
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
        payment_method: str,
        payment_gateway: Optional[str] = None,
        return_url: Optional[str] = None,
        guest_id: Optional[uuid.UUID] = None,
        advance_amount: Optional[float] = None,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> dict:
        try:
            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None:
                raise BookingException("Booking not found")
            if guest_id is not None and booking.guest_id != guest_id:
                raise BookingException("Booking not found")
            if booking.status == "EXPIRED":
                raise BookingException(
                    "This booking has expired. Please search and reserve again."
                )
            if booking.status == "CONFIRMED":
                raise BookingException("This booking has already been confirmed.")
            if booking.status != "PENDING":
                raise BookingException(
                    f"Booking is in status {booking.status}, cannot proceed to payment"
                )

            payment_method_upper = payment_method.upper()

            # Handle PAY_ON_ARRIVAL
            if payment_method_upper == "PAY_ON_ARRIVAL":
                property_obj = await self.property_repo.get_by_id(booking.property_id)
                if not property_obj.allow_pay_on_arrival:
                    raise BookingException(
                        "This property does not accept pay-on-arrival payments"
                    )

                # Confirm booking immediately
                await self.booking_repo.try_confirm_booking(
                    ref_number=ref_number,
                    payment_status=PaymentStatus.UNPAID,
                    payment_method=PaymentMethod.PAY_ON_ARRIVAL,
                    amount_paid=Decimal("0.00"),
                    amount_due=booking.total_amount,
                )
                await self.db.commit()

                # Clear soft-lock
                await self.redis.delete(f"booking:softlock:{booking.id}")

                # Send confirmation emails
                if background_tasks:
                    background_tasks.add_task(self.send_confirmation_emails, ref_number)

                return {
                    "status": "CONFIRMED",
                    "amount": float(booking.total_amount),
                    "currency": property_obj.currency,
                    "payment_status": str(booking.payment_status),
                    "amount_paid": float(booking.amount_paid),
                    "amount_due": float(booking.amount_due),
                    "message": "Booking confirmed. Payment due on arrival.",
                    "ref_number": ref_number,
                    "payment_method": "PAY_ON_ARRIVAL",
                }

            # For ONLINE and ADVANCE, gateway is required
            if payment_gateway is None:
                raise BookingException(
                    "payment_gateway is required for ONLINE and ADVANCE payments"
                )

            try:
                PGEnum(payment_gateway.upper())
            except ValueError:
                raise UnsupportedGatewayError(
                    internal_detail=f"Unsupported payment gateway: {payment_gateway}"
                )

            # Handle ADVANCE
            payment_amount = booking.total_amount
            if payment_method_upper == "ADVANCE":
                if advance_amount is None:
                    raise BookingException(
                        "advance_amount is required for ADVANCE payments"
                    )
                advance_decimal = Decimal(str(advance_amount))

                # Get property-specific advance rules
                property_for_advance = await self.property_repo.get_by_id(booking.property_id)
                min_pct = getattr(property_for_advance, "min_advance_percentage", None) or 10
                max_pct = getattr(property_for_advance, "max_advance_percentage", None) or 50

                min_advance = (booking.total_amount * Decimal(min_pct) / Decimal(100)).quantize(
                    Decimal("0.01")
                )
                max_advance = (booking.total_amount * Decimal(max_pct) / Decimal(100)).quantize(
                    Decimal("0.01")
                )
                if advance_decimal < min_advance:
                    raise BookingException(
                        f"Advance amount must be at least {min_advance} ({min_pct}% of total)"
                    )
                if advance_decimal > max_advance:
                    raise BookingException(
                        f"Advance amount cannot exceed {max_advance} ({max_pct}% of total)"
                    )
                payment_amount = advance_decimal
                await self.booking_repo.set_advance_amount(ref_number, advance_decimal)
                await self.db.commit()

            # Handle Khalti return URL validation
            if payment_gateway.upper() == "KHALTI":
                if not return_url:
                    raise UrlValidationException(
                        "Return url is required for Khalti payments"
                    )
                try:
                    return_url = validate_khalti_return_url(return_url)
                except ValueError as e:
                    raise UrlValidationException(str(e))

            # Set payment method on booking
            await self.booking_repo.set_payment_method(ref_number, payment_method_upper)
            await self.db.commit()

            # Set payment gateway
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
                amount=payment_amount,
                currency=currency,
                return_url=return_url,
            )

            return {
                "ref_number": ref_number,
                "payment_gateway": payment_gateway,
                "payment_method": payment_method_upper,
                "amount": float(payment_amount),
                "currency": currency,
                **intent_data,
            }

        except (
            UnsupportedGatewayError,
            PaymentGatewayError,
            ServiceException,
            BookingException,
            UrlValidationException,
            InvalidReturnUrl,
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
            rooms = await self._fetch_rooms_for_booking(booking)
            nights = (booking.checkout_date - booking.checkin_date).days
            rooms_data = self._build_rooms_data(rooms, nights)
            soft_lock_expires_at = await self._get_soft_lock_expiry(booking.id)

            return self._build_full_booking_response(
                booking=booking,
                property_obj=property_obj,
                rooms_data=rooms_data,
                nights=nights,
                soft_lock_expires_at=soft_lock_expires_at,
            )

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
            booking_items = [
                {
                    "id": b.id,
                    "property_id": b.property_id,
                    "property_name": b.property.name,
                    "property_photo": b.property.photos.get("cover")
                    if b.property.photos
                    else None,
                    "ref_number": b.ref_number,
                    "status": b.status.value
                    if hasattr(b.status, "value")
                    else b.status,
                    "number_of_adults": b.number_of_adults,
                    "number_of_children": b.number_of_children,
                    "checkin_date": b.checkin_date,
                    "checkout_date": b.checkout_date,
                    "total_amount": float(b.total_amount),
                    "currency": b.property.currency,
                    "created_at": b.created_at,
                }
                for b in bookings
            ]
            return {"bookings": booking_items, "total": total}

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
            coupon_discount = min(coupon_discount, total_after_offers).quantize(
                Decimal("0.01")
            )

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
            rooms = await self._fetch_rooms_for_booking(booking)
            rooms_data = self._build_rooms_data(rooms, nights)
            soft_lock_expires_at = await self._get_soft_lock_expiry(updated.id)

            return self._build_full_booking_response(
                booking=updated,
                property_obj=property_obj,
                rooms_data=rooms_data,
                nights=nights,
                soft_lock_expires_at=soft_lock_expires_at,
                number_of_adults=booking.number_of_adults,
                number_of_children=booking.number_of_children,
            )

        except (BookingException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error applying discount to {ref_number}: {e}"
            )
            raise ServiceException("Could not apply discount code.")

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

    async def send_confirmation_emails(self, ref_number: str) -> None:
        logger.info(f"[BookingService] Sending confirmation emails for {ref_number}")
        async with AsyncSessionLocal() as session:
            try:
                fresh_booking_repo = BookingRepository(session)
                booking = await fresh_booking_repo.get_by_ref_with_details(ref_number)

                if booking is None:
                    logger.error(
                        f"[BookingService] Could not send emails — booking {ref_number} not found"
                    )
                    return

                property_obj = booking.property
                guest = booking.guest
                room_units = [br.room_unit for br in booking.booking_rooms]

                await send_booking_confirmed_guest_email(
                    to_email=guest.email,
                    guest_name=guest.full_name,
                    guest_phone_number=guest.phone,
                    booking=booking,
                    property_obj=property_obj,
                    room_units=room_units,
                )

                await send_booking_confirmed_owner_email(
                    to_email=property_obj.email,
                    owner_name=property_obj.name,
                    guest_name=guest.full_name,
                    guest_email=guest.email,
                    guest_phone=guest.phone,
                    guest_nationality=guest.nationality,
                    booking=booking,
                    property_obj=property_obj,
                    room_units=room_units,
                )

            except Exception as e:
                logger.error(
                    f"[BookingService] Failed to send confirmation emails for {ref_number}: {e}"
                )
                # Deliberately swallowed — runs after the response is already sent.

    async def delete_booking(self, ref_number: str, guest_id: uuid.UUID) -> dict:
        try:
            # 1. Fire a single atomic delete query to the database
            deleted_booking = await self.booking_repo.delete_booking(
                ref_number, guest_id
            )

            # 2. Check if the booking even existed for this specific guest
            if not deleted_booking:
                raise BookingException("Booking not found")

            # 3. Check the snapshot status of the row that was actually deleted
            # Note: If your Enum stores string values, compare directly to the string or Enum property
            allowed_statuses = {"PENDING", "EXPIRED"}
            if deleted_booking["status"] not in allowed_statuses:
                # Explicitly roll back because the record was prematurely impacted
                await self.db.rollback()
                raise BookingException(
                    "Only pending or expired bookings can be cancelled"
                )

            # 4. Safely clear Redis using the confirmed deleted ID
            booking_id = deleted_booking["id"]
            await self.redis.delete(f"booking:softlock:{booking_id}")

            # 5. Commit transaction
            await self.db.commit()

            return {"success": True, "data": "Booking deleted successfully"}

        except (BookingException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[BookingService] Failed to cancel booking {ref_number}: {e}")
            raise ServiceException("Could not cancel booking. Please try again.")

    async def update_special_requests(
        self, ref_number: str, guest_id: uuid.UUID, special_requests: str
    ) -> dict:
        try:
            # 1. Run the single atomic update query
            updated_booking = await self.booking_repo.update_special_requests(
                ref_number, guest_id, special_requests
            )

            # 2. If it returns None, either it doesn't exist OR it exists but isn't PENDING
            if updated_booking is None:
                # Quick check to provide an accurate exception message to the user
                exists = await self.booking_repo.get_by_ref(ref_number)
                if exists and exists.guest_id == guest_id:
                    raise BookingException("Only pending bookings can be updated.")
                raise BookingException("Booking not found")

            # 3. Securely commit changes to disk
            await self.db.commit()

            # 4. Convert your fully pre-loaded ORM object into your response payload dictionary format
            return {
                "success": True,
                "message": "Special requests updated successfully.",
            }

        except (BookingException, ServiceException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error updating special requests for {ref_number}: {e}"
            )
            raise ServiceException("Could not update special requests.")

    async def pay_remaining_balance(
        self,
        ref_number: str,
        guest_id: uuid.UUID,
        payment_gateway: str,
        gateway_payload: dict,
        idempotency_key: str,
        return_url: Optional[str] = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        """
        Allows a guest to pay the remaining balance on a CONFIRMED booking
        that was made with ADVANCE or PAY_ON_ARRIVAL payment method.
        """
        try:
            try:
                PGEnum(payment_gateway.upper())
            except ValueError:
                raise UnsupportedGatewayError(
                    internal_detail=f"Unsupported payment gateway: {payment_gateway}"
                )

            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None or booking.guest_id != guest_id:
                raise BookingException("Booking not found")

            if booking.status != MasterBookingStatus.CONFIRMED:
                raise BookingException(
                    "Only confirmed bookings can have remaining balance paid"
                )

            if booking.payment_status == PaymentStatus.PAID:
                raise BookingException("Booking is already fully paid")

            if booking.amount_due <= Decimal("0"):
                raise BookingException("No remaining balance to pay")

            # Verify payment with gateway
            payment_verified = await self.payment_service.verify(
                payment_gateway, ref_number, gateway_payload
            )
            if not payment_verified:
                return {
                    "status": "PAYMENT_NOT_VERIFIED",
                    "message": "Payment could not be verified.",
                }

            # Mark as fully paid
            await self.booking_repo.set_fully_paid(ref_number)
            await self.db.commit()

            return {
                "status": "PAID",
                "message": "Remaining balance paid successfully",
                "booking_id": str(booking.id),
                "ref_number": booking.ref_number,
            }

        except (UnsupportedGatewayError, BookingException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error paying remaining balance for {ref_number}: {e}"
            )
            raise ServiceException("Could not process payment. Please try again.")

    async def record_staff_payment(
        self,
        ref_number: str,
        amount: float,
        payment_method_name: str,
        notes: str | None = None,
    ) -> dict:
        """
        Records a staff-collected payment (cash, card terminal, etc.) at check-in.
        """
        try:
            booking = await self.booking_repo.get_by_ref(ref_number)

            if booking is None:
                raise BookingException("Booking not found")

            if booking.status != MasterBookingStatus.CONFIRMED:
                raise BookingException(
                    "Only confirmed bookings can have payments recorded"
                )

            if booking.payment_status == PaymentStatus.PAID:
                raise BookingException("Booking is already fully paid")

            if amount <= 0:
                raise BookingException("Payment amount must be positive")

            if Decimal(str(amount)) > booking.amount_due:
                raise BookingException(
                    f"Payment amount ({amount}) exceeds remaining balance ({booking.amount_due})"
                )

            updated_booking = await self.booking_repo.record_staff_payment(
                ref_number=ref_number,
                amount=Decimal(str(amount)),
                payment_method_name=payment_method_name,
                notes=notes,
            )

            if updated_booking is None:
                raise BookingException("Booking not found")

            await self.db.commit()

            return {
                "success": True,
                "message": f"Payment of {amount} recorded successfully",
                "amount_paid": float(updated_booking.amount_paid),
                "amount_due": float(updated_booking.amount_due),
                "payment_status": updated_booking.payment_status.value,
            }

        except (BookingException, RepositoryException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[BookingService] Error recording staff payment for {ref_number}: {e}"
            )
            raise ServiceException("Could not record payment. Please try again.")
