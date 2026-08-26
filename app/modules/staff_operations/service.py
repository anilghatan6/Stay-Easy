import uuid
from datetime import date, datetime, timezone,timedelta
from decimal import Decimal
import math
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff_operations.repository import StaffOperationsRepository
from app.modules.pms.models.rooms_model import RoomStatus
from app.modules.booking.models.booking_model import MasterBookingStatus, PaymentStatus
from app.modules.auth.models.users_model import User
from app.utils.exceptions import (
    BookingException,
    InvalidDateException,
    PermissionException,
    ServiceException,
    RoomsUnavailableError,
)
from app.utils.logging import LoggerFactory
from app.modules.staff_operations.schemas import ModifyBookingRequest
logger = LoggerFactory.get_logger(__name__)


class StaffOperationsService:
    def __init__(
        self,
        db: AsyncSession,
        staff_ops_repo: StaffOperationsRepository,
        room_repo,
        offer_repo,
    ):
        self.db = db
        self.staff_ops_repo = staff_ops_repo
        self.room_repo = room_repo
        self.offer_repo = offer_repo

    async def _verify_staff_property_assignment(
        self, staff_user: User, property_id: uuid.UUID
    ) -> None:
        """Verify the staff member is assigned to the property. Raises if not."""
        staff_record = await self.staff_ops_repo.get_staff_by_email(staff_user.email)
        if staff_record is None:
            raise PermissionException("Staff record not found for this user")

        assigned = await self.staff_ops_repo.is_staff_assigned_to_property(
            staff_record.id, property_id
        )
        if not assigned:
            raise PermissionException(
                "You are not assigned to this property"
            )

    def _build_room_info(self, room) -> dict:
        return {
            "room_id": room.id,
            "room_name": room.room_name,
            "room_type": room.room_type.room_type_name if room.room_type else "",
            "bed_type": room.bed_type.bed_name if room.bed_type else "",
            "base_rate": float(room.base_rate),
        }

    async def get_booking_for_staff(
        self, ref_number: str, staff_user: User
    ) -> dict:
        """Get booking detail for staff, verifying property assignment."""
        logger.info(f"[StaffOperationsService] Getting booking {ref_number} for staff")
        try:
            booking = await self.staff_ops_repo.get_booking_by_ref_with_details(ref_number)
            if booking is None:
                raise BookingException("Booking not found")

            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(staff_user, booking.property_id)

            rooms = [br.room_unit for br in booking.booking_rooms if br.room_unit]
            rooms_data = [self._build_room_info(r) for r in rooms]

            property_obj = booking.property
            guest = booking.guest

            return {
                "booking_id": booking.id,
                "ref_number": booking.ref_number,
                "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
                "payment_status": booking.payment_status.value if hasattr(booking.payment_status, "value") else booking.payment_status,
                "payment_method": booking.payment_method.value if hasattr(booking.payment_method, "value") else booking.payment_method,
                "amount_paid": float(booking.amount_paid),
                "amount_due": float(booking.amount_due),
                "number_of_adults": booking.number_of_adults,
                "number_of_children": booking.number_of_children,
                "checkin_date": booking.checkin_date,
                "checkout_date": booking.checkout_date,
                "checked_in_at": booking.checked_in_at,
                "checked_out_at": booking.checked_out_at,
                "special_requests": booking.special_requests,
                "property": {
                    "property_id": property_obj.id,
                    "name": property_obj.name,
                    "check_in_time": property_obj.check_in_time,
                    "check_out_time": property_obj.check_out_time,
                    "always_allow_check_in_out": property_obj.always_allow_check_in_out,
                },
                "rooms": rooms_data,
                "guest": {
                    "guest_id": guest.id,
                    "full_name": guest.full_name,
                    "email": guest.email,
                    "phone": guest.phone,
                },
                "total_amount": float(booking.total_amount),
                "created_at": booking.created_at,
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting booking {ref_number}: {e}"
            )
            raise ServiceException("Could not fetch booking details.")

    async def check_in_guest(
        self, ref_number: str, staff_user: User
    ) -> dict:
        """Check in a guest. Validates booking status and staff assignment."""
        logger.info(f"[StaffOperationsService] Checking in {ref_number}")
        try:
            booking = await self.staff_ops_repo.get_booking_by_ref_with_details(ref_number)
            if booking is None:
                raise BookingException("Booking not found")

            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(staff_user, booking.property_id)

            property_obj = booking.property
            today = datetime.now(timezone.utc).date()

            # Validate check-in date (unless always_allow_check_in_out is set)
            if not property_obj.always_allow_check_in_out:
                if booking.checkin_date != today:
                    raise BookingException(
                        f"Check-in date mismatch. Expected {booking.checkin_date}, got {today}"
                    )

            # Try atomic status transition
            checked_in = await self.staff_ops_repo.try_check_in_booking(ref_number)
            if checked_in is None:
                raise BookingException(
                    "Booking cannot be checked in. Status must be CONFIRMED."
                )

            # Update room statuses to OCCUPIED
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            if room_ids:
                await self.staff_ops_repo.update_rooms_status(room_ids, RoomStatus.OCCUPIED)

            await self.db.commit()

            # Build response
            rooms = [br.room_unit for br in booking.booking_rooms if br.room_unit]
            rooms_data = [self._build_room_info(r) for r in rooms]

            return {
                "ref_number": ref_number,
                "status": MasterBookingStatus.CHECKED_IN.value,
                "checked_in_at": checked_in.checked_in_at,
                "property_name": property_obj.name,
                "rooms": rooms_data,
                "guest_name": booking.guest.full_name,
                "message": "Guest checked in successfully",
            }

        except (BookingException, PermissionException):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[StaffOperationsService] Error checking in {ref_number}: {e}"
            )
            raise ServiceException("Could not check in guest. Please try again.")

    async def check_out_guest(
        self, ref_number: str, staff_user: User
    ) -> dict:
        """Check out a guest. Validates booking status and staff assignment."""
        logger.info(f"[StaffOperationsService] Checking out {ref_number}")
        try:
            booking = await self.staff_ops_repo.get_booking_by_ref_with_details(ref_number)
            if booking is None:
                raise BookingException("Booking not found")

            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(staff_user, booking.property_id)

            property_obj = booking.property
            today = datetime.now(timezone.utc).date()

            # Validate check-out date (unless always_allow_check_in_out is set)
            if not property_obj.always_allow_check_in_out:
                if booking.checkout_date != today:
                    raise BookingException(
                        f"Check-out date mismatch. Expected {booking.checkout_date}, got {today}"
                    )

            # Try atomic status transition
            checked_out = await self.staff_ops_repo.try_check_out_booking(ref_number)
            if checked_out is None:
                raise BookingException(
                    "Booking cannot be checked out. Status must be CHECKED_IN."
                )

            # Update room statuses to DIRTY (needs cleaning after guest departure)
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            if room_ids:
                await self.staff_ops_repo.update_rooms_status(room_ids, RoomStatus.DIRTY)

            await self.db.commit()

            # Build response
            rooms = [br.room_unit for br in booking.booking_rooms if br.room_unit]
            rooms_data = [self._build_room_info(r) for r in rooms]

            return {
                "ref_number": ref_number,
                "status": MasterBookingStatus.CHECKED_OUT.value,
                "checked_out_at": checked_out.checked_out_at,
                "property_name": property_obj.name,
                "rooms": rooms_data,
                "guest_name": booking.guest.full_name,
                "amount_due": float(booking.amount_due),
                "message": "Guest checked out successfully",
            }

        except (BookingException, PermissionException):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[StaffOperationsService] Error checking out {ref_number}: {e}"
            )
            raise ServiceException("Could not check out guest. Please try again.")


    async def _calculate_stay_total(
        self,
        room_ids: list[uuid.UUID],
        checkin_date: date,
        checkout_date: date,
    ) -> Decimal:
        """
        Recalculates the subtotal for a stay: sum of each room's base_rate,
        multiplied by number of nights. Mirrors the pricing logic used in
        property search (see PropertySearchService candidate scoring).
        """
        nights = (checkout_date - checkin_date).days
        if nights <= 0:
            raise BookingException("checkout_date must be after checkin_date")

        rooms = await self.staff_ops_repo.get_rooms_by_ids(room_ids)

        if len(rooms) != len(room_ids):
            found_ids = {r.id for r in rooms}
            missing = [str(rid) for rid in room_ids if rid not in found_ids]
            raise BookingException(f"Room(s) not found.")

        subtotal = sum(room.base_rate for room in rooms) * nights
        return Decimal(subtotal)

    async def modify_booking(
        self, ref_number: str, staff_user: User, payload: ModifyBookingRequest
    ) -> dict:
        logger.info(f"[StaffOperationsService] Modifying booking {ref_number}")
        try:
            booking = await self.staff_ops_repo.get_booking_by_ref_with_details(ref_number)
            if booking is None:
                raise BookingException("Booking not found")

            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(staff_user, booking.property_id)

            if booking.status in (
                MasterBookingStatus.CHECKED_OUT,
                MasterBookingStatus.CANCELLED,
                MasterBookingStatus.EXPIRED,
            ):
                raise BookingException(
                    f"Cannot modify booking in status {booking.status}"
                )

            # CHECKED_IN bookings: only checkout_date (extension) is allowed
            if booking.status == MasterBookingStatus.CHECKED_IN:
                if payload.checkin_date or payload.room_unit_ids:
                    raise BookingException(
                        "Guest is already checked in — only checkout date can be extended"
                    )

            new_checkin = payload.checkin_date or booking.checkin_date
            new_checkout = payload.checkout_date or booking.checkout_date
            new_room_ids = payload.room_unit_ids or [
                br.room_unit_id for br in booking.booking_rooms
            ]
            new_adults = payload.number_of_adults or booking.number_of_adults
            new_children = payload.number_of_children or booking.number_of_children

            dates_changed = (new_checkin != booking.checkin_date) or (new_checkout != booking.checkout_date)
            rooms_changed = payload.room_unit_ids is not None
            occupants_changed = (
                payload.number_of_adults is not None or payload.number_of_children is not None
            )

            # 1. Capacity check — only needed if rooms or occupant counts changed
            if rooms_changed or occupants_changed:
                await self._validate_room_capacity(
                    room_ids=new_room_ids, adults=new_adults, children=new_children
                )

            # 2. Availability check — only needed if dates or rooms actually changed
            if dates_changed or rooms_changed:
                conflicts = await self.staff_ops_repo.check_rooms_available(
                    new_room_ids, new_checkin, new_checkout, exclude_booking_id=booking.id
                )
                if conflicts:
                    raise BookingException(f"Room(s) unavailable for selected dates: {conflicts}")

            # 3. Recalculate pricing
            new_subtotal = await self._calculate_stay_total(
                room_ids=new_room_ids, checkin_date=new_checkin, checkout_date=new_checkout
            )
            new_total = new_subtotal - booking.special_offer_discount - booking.coupon_discount
            if new_total < 0:
                new_total = Decimal("0.00")

            # 3. Reconcile payment
            amount_paid = booking.amount_paid
            if new_total > amount_paid:
                amount_due = new_total - amount_paid
                refund_due = Decimal("0.00")
                payment_status = (
                    PaymentStatus.PARTIAL if amount_paid > 0 else PaymentStatus.UNPAID
                )
            elif new_total < amount_paid:
                amount_due = Decimal("0.00")
                refund_due = amount_paid - new_total
                payment_status = PaymentStatus.PAID  # fully covered, refund owed on top
            else:
                amount_due = Decimal("0.00")
                refund_due = Decimal("0.00")
                payment_status = PaymentStatus.PAID

            # 4. Apply changes via repo (single UPDATE, avoids partial-write races)
            updated = await self.staff_ops_repo.apply_booking_modification(
                booking=booking,
                staff_id=staff_user.id,
                checkin_date=new_checkin,
                checkout_date=new_checkout,
                new_room_ids=new_room_ids if rooms_changed else None,
                number_of_adults=payload.number_of_adults,
                number_of_children=payload.number_of_children,
                special_requests=payload.special_requests,
                subtotal=new_subtotal,
                total_amount=new_total,
                amount_due=amount_due,
                refund_due=refund_due,
                payment_status=payment_status,
                reason=payload.reason,
            )

            await self.db.commit()
            await self.db.refresh(updated)

            message = "Booking updated successfully."
            if refund_due > 0:
                message += f" Refund of {refund_due} is owed to the guest — process via payment gateway."
            elif amount_due > 0:
                message += f" Additional {amount_due} is due from the guest."

            return {
                "ref_number": ref_number,
                "checkin_date": updated.checkin_date,
                "checkout_date": updated.checkout_date,
                "total_amount": updated.total_amount,
                "amount_paid": updated.amount_paid,
                "amount_due": updated.amount_due,
                "refund_due": updated.refund_due,
                "payment_status": updated.payment_status.value,
                "message": message,
            }

        except (BookingException, PermissionException):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[StaffOperationsService] Error modifying {ref_number}: {e}")
            raise ServiceException("Could not modify booking. Please try again.")

    async def _validate_room_capacity(
        self,
        room_ids: list[uuid.UUID],
        adults: int,
        children: int,
    ) -> None:
        """
        Ensures the selected rooms can accommodate the given occupants.
        Mirrors the per-room capacity split used in property search:
        occupants are divided evenly across the selected rooms, and each
        room must individually meet its share of max_adults/max_children.
        """
        rooms = await self.staff_ops_repo.get_rooms_by_ids(room_ids)

        if len(rooms) != len(room_ids):
            found_ids = {r.id for r in rooms}
            missing = [str(rid) for rid in room_ids if rid not in found_ids]
            raise BookingException(f"Room(s) not found: {', '.join(room_names)}")

        rooms_needed = len(room_ids)
        adults_per_room = math.ceil(adults / rooms_needed)
        children_per_room = math.ceil(children / rooms_needed)

        insufficient = [
            room
            for room in rooms
            if room.max_adults < adults_per_room or room.max_children < children_per_room
        ]

        if insufficient:
            # room_names = await self.room_repo.get_by_ids_with_details(insufficient)
            raise BookingException(
                f"Selected room(s) cannot accommodate {adults} adult(s) and "
                f"{children} child(ren) across {rooms_needed} room(s)."
            )
        
