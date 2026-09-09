import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import math
import secrets
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff_operations.repository import StaffOperationsRepository
from app.modules.booking.repositories.booking_repository import BookingRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.pms.models.rooms_model import RoomStatus
from app.modules.pms.models.activity_log_model import PropertyActivityLog
from app.modules.booking.models.booking_model import (
    MasterBookingStatus,
    PaymentMethod,
    PaymentStatus,
    BookingType,
)
from app.modules.auth.models.users_model import User
from app.modules.booking.models.booking_modification_log import BookingModificationLog
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
        booking_repo: BookingRepository,
        room_repo: RoomRepository,
        property_repo: PropertyRepository,
        offer_repo: SpecialOfferRepository,
        discount_code_repo: DiscountCodeRepository,
        redis_client,
    ):
        self.db = db
        self.staff_ops_repo = staff_ops_repo
        self.booking_repo = booking_repo
        self.room_repo = room_repo
        self.property_repo = property_repo
        self.offer_repo = offer_repo
        self.discount_code_repo = discount_code_repo
        self.redis = redis_client

    async def _log_activity(
        self,
        property_id: uuid.UUID,
        staff_id: uuid.UUID,
        staff_name: str,
        activity_type: str,
        description: str,
        booking_id: Optional[uuid.UUID] = None,
        room_id: Optional[uuid.UUID] = None,
        extra_data: Optional[dict] = None,
    ) -> None:
        """Log a property activity for the activity feed."""
        self.db.add(
            PropertyActivityLog(
                property_id=property_id,
                staff_id=staff_id,
                staff_name=staff_name,
                activity_type=activity_type,
                description=description,
                booking_id=booking_id,
                room_id=room_id,
                extra_data=extra_data,
            )
        )

    async def _get_staff_name(self, staff_user: User) -> str:
        """Resolve staff display name from the User object."""
        staff_record = await self.staff_ops_repo.get_staff_by_email(staff_user.email)
        if staff_record:
            return staff_record.full_name
        return staff_user.full_name or staff_user.email

    # Activity type constants
    BOOKING_ACTIVITY_TYPES = [
        "WALKIN_BOOKING",
        "CHECK_IN",
        "CHECK_OUT",
        "BOOKING_MODIFIED",
        "BOOKING_CANCELLED",
        "ROOM_STATUS_CHANGE",
    ]
    HOUSEKEEPING_ACTIVITY_TYPES = [
        "TASK_CREATED",
        "TASK_COMPLETED",
        "TASK_STATUS_UPDATE",
        "CLEANING_SUBMITTED",
        "CLEANING_REVIEWED",
    ]

    async def _verify_property_access(
        self, property_id: uuid.UUID, staff_user: User
    ) -> None:
        """Verify staff has access to the property."""
        if staff_user.role != "admin":
            await self._verify_staff_property_assignment(staff_user, property_id)

    async def get_booking_activities(
        self,
        property_id: uuid.UUID,
        staff_user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PropertyActivityLog], int]:
        """Get paginated booking & front desk activity logs for a property."""
        logger.info(
            f"[StaffOperationsService] Getting booking activities for property {property_id}"
        )
        try:
            await self._verify_property_access(property_id, staff_user)

            logs, total_count = await self.staff_ops_repo.get_property_activity_logs(
                property_id=property_id,
                skip=skip,
                limit=limit,
                activity_types=self.BOOKING_ACTIVITY_TYPES,
            )
            return logs, total_count

        except PermissionException:
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting booking activities for property {property_id}: {e}"
            )
            raise ServiceException("Could not fetch booking activity logs.")

    async def get_housekeeping_activities(
        self,
        property_id: uuid.UUID,
        staff_user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PropertyActivityLog], int]:
        """Get paginated housekeeping activity logs for a property."""
        logger.info(
            f"[StaffOperationsService] Getting housekeeping activities for property {property_id}"
        )
        try:
            await self._verify_property_access(property_id, staff_user)

            logs, total_count = await self.staff_ops_repo.get_property_activity_logs(
                property_id=property_id,
                skip=skip,
                limit=limit,
                activity_types=self.HOUSEKEEPING_ACTIVITY_TYPES,
            )
            return logs, total_count

        except PermissionException:
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting housekeeping activities for property {property_id}: {e}"
            )
            raise ServiceException("Could not fetch housekeeping activity logs.")

    async def get_todays_arrivals(
        self,
        property_id: uuid.UUID,
        staff_user: User,
    ) -> list[dict]:
        """Get all bookings checking in today for a property."""
        logger.info(
            f"[StaffOperationsService] Getting today's arrivals for property {property_id}"
        )
        try:
            await self._verify_property_access(property_id, staff_user)

            today = datetime.now(timezone.utc).date()
            bookings = await self.staff_ops_repo.get_todays_arrivals(
                property_id=property_id,
                today=today,
            )

            return [self._build_front_desk_booking(b) for b in bookings]

        except PermissionException:
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting today's arrivals: {e}"
            )
            raise ServiceException("Could not fetch today's arrivals.")

    async def get_todays_departures(
        self,
        property_id: uuid.UUID,
        staff_user: User,
    ) -> list[dict]:
        """Get all bookings checking out today for a property."""
        logger.info(
            f"[StaffOperationsService] Getting today's departures for property {property_id}"
        )
        try:
            await self._verify_property_access(property_id, staff_user)

            today = datetime.now(timezone.utc).date()
            bookings = await self.staff_ops_repo.get_todays_departures(
                property_id=property_id,
                today=today,
            )

            return [self._build_front_desk_booking(b) for b in bookings]

        except PermissionException:
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting today's departures: {e}"
            )
            raise ServiceException("Could not fetch today's departures.")

    async def get_front_desk_summary(
        self,
        property_id: uuid.UUID,
        staff_user: User,
    ) -> dict:
        """Get summary counts for front desk dashboard."""
        logger.info(
            f"[StaffOperationsService] Getting front desk summary for property {property_id}"
        )
        try:
            await self._verify_property_access(property_id, staff_user)

            today = datetime.now(timezone.utc).date()
            summary = await self.staff_ops_repo.get_front_desk_summary(
                property_id=property_id,
                today=today,
            )
            return summary

        except PermissionException:
            raise
        except Exception as e:
            logger.error(
                f"[StaffOperationsService] Error getting front desk summary: {e}"
            )
            raise ServiceException("Could not fetch front desk summary.")

    def _build_front_desk_booking(self, booking) -> dict:
        """Build a front desk booking response from a Booking object."""
        guest = None
        if booking.guest:
            guest = {
                "guest_id": booking.guest.id,
                "full_name": booking.guest.full_name,
                "email": booking.guest.email,
                "phone": booking.guest.phone,
                "nationality": booking.guest.nationality,
            }
        elif booking.booking_guest:
            guest = {
                "guest_id": None,
                "full_name": booking.booking_guest.full_name,
                "email": booking.booking_guest.email,
                "phone": booking.booking_guest.phone,
                "nationality": booking.booking_guest.nationality,
            }

        rooms = [
            {
                "room_id": br.room_unit.id,
                "room_name": br.room_unit.room_name,
                "room_type": br.room_unit.room_type.room_type_name if br.room_unit.room_type else "",
                "bed_type": br.room_unit.bed_type.bed_name if br.room_unit.bed_type else "",
                "base_rate": float(br.room_unit.base_rate),
            }
            for br in booking.booking_rooms
            if br.room_unit
        ]

        return {
            "booking_id": booking.id,
            "ref_number": booking.ref_number,
            "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
            "booking_type": booking.booking_type.value if hasattr(booking.booking_type, "value") else booking.booking_type,
            "guest": guest,
            "rooms": rooms,
            "checkin_date": booking.checkin_date,
            "checkout_date": booking.checkout_date,
            "number_of_adults": booking.number_of_adults,
            "number_of_children": booking.number_of_children,
            "special_requests": booking.special_requests,
            "payment_method": booking.payment_method.value if hasattr(booking.payment_method, "value") else booking.payment_method,
            "payment_status": booking.payment_status.value if hasattr(booking.payment_status, "value") else booking.payment_status,
            "payment_gateway": booking.payment_gateway.value if booking.payment_gateway and hasattr(booking.payment_gateway, "value") else booking.payment_gateway,
            "amount_paid": float(booking.amount_paid),
            "amount_due": float(booking.amount_due),
            "advance_amount": float(booking.advance_amount) if booking.advance_amount else None,
            "total_amount": float(booking.total_amount),
            "created_at": booking.created_at,
        }

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

    def _generate_ref_number(self) -> str:
        return f"BK-{secrets.token_hex(4).upper()}"

    def _build_guest_info(self, booking) -> dict | None:
        """Build guest info from either authenticated Guest or BookingGuest."""
        if booking.guest:
            return {
                "guest_id": booking.guest.id,
                "full_name": booking.guest.full_name,
                "email": booking.guest.email,
                "phone": booking.guest.phone,
            }
        if booking.booking_guest:
            return {
                "booking_guest_id": booking.booking_guest.id,
                "full_name": booking.booking_guest.full_name,
                "email": booking.booking_guest.email,
                "phone": booking.booking_guest.phone,
                "nationality": booking.booking_guest.nationality,
            }
        return None

    def _resolve_guest_name(self, booking) -> str:
        """Get guest name from either authenticated Guest or BookingGuest."""
        if booking.guest:
            return booking.guest.full_name
        if booking.booking_guest:
            return booking.booking_guest.full_name
        return "Unknown"

    def _build_property_info(self, property_obj) -> dict:
        return {
            "property_id": property_obj.id,
            "name": property_obj.name,
            "check_in_time": property_obj.check_in_time,
            "check_out_time": property_obj.check_out_time,
            "always_allow_check_in_out": property_obj.always_allow_check_in_out,
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

            return {
                "booking_id": booking.id,
                "ref_number": booking.ref_number,
                "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
                "booking_type": booking.booking_type.value if hasattr(booking.booking_type, "value") else booking.booking_type,
                "payment_status": booking.payment_status.value if hasattr(booking.payment_status, "value") else booking.payment_status,
                "payment_method": booking.payment_method.value if hasattr(booking.payment_method, "value") else booking.payment_method,
                "amount_paid": float(booking.amount_paid),
                "amount_due": float(booking.amount_due),
                "refund_due": float(booking.refund_due),
                "number_of_adults": booking.number_of_adults,
                "number_of_children": booking.number_of_children,
                "checkin_date": booking.checkin_date,
                "checkout_date": booking.checkout_date,
                "checked_in_at": booking.checked_in_at,
                "checked_out_at": booking.checked_out_at,
                "special_requests": booking.special_requests,
                "coupon_code": booking.coupon_code,
                "coupon_discount": float(booking.coupon_discount),
                "property": self._build_property_info(booking.property),
                "rooms": rooms_data,
                "guest": self._build_guest_info(booking) if not booking.booking_guest else None,
                "booking_guest": self._build_guest_info(booking) if booking.booking_guest else None,
                "total_amount": float(booking.total_amount),
                "subtotal": float(booking.subtotal),
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
            staff_name = await self._get_staff_name(staff_user)
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            if room_ids:
                await self.staff_ops_repo.update_rooms_status(
                    room_ids, RoomStatus.OCCUPIED,
                    property_id=booking.property_id,
                    staff_id=staff_user.id,
                    staff_name=staff_name,
                    old_status=RoomStatus.AVAILABLE,
                )

            # Log check-in activity
            await self._log_activity(
                property_id=booking.property_id,
                staff_id=staff_user.id,
                staff_name=staff_name,
                activity_type="CHECK_IN",
                description=f"Guest {self._resolve_guest_name(booking)} checked in",
                booking_id=booking.id,
                extra_data={
                    "guest_name": self._resolve_guest_name(booking),
                    "room_names": [br.room_unit.room_name for br in booking.booking_rooms if br.room_unit],
                },
            )

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
                "guest_name": self._resolve_guest_name(booking),
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
            staff_name = await self._get_staff_name(staff_user)
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            if room_ids:
                await self.staff_ops_repo.update_rooms_status(
                    room_ids, RoomStatus.DIRTY,
                    property_id=booking.property_id,
                    staff_id=staff_user.id,
                    staff_name=staff_name,
                    old_status=RoomStatus.OCCUPIED,
                )

            # Log check-out activity
            await self._log_activity(
                property_id=booking.property_id,
                staff_id=staff_user.id,
                staff_name=staff_name,
                activity_type="CHECK_OUT",
                description=f"Guest {self._resolve_guest_name(booking)} checked out",
                booking_id=booking.id,
                extra_data={
                    "guest_name": self._resolve_guest_name(booking),
                    "room_names": [br.room_unit.room_name for br in booking.booking_rooms if br.room_unit],
                    "amount_due": float(booking.amount_due),
                },
            )

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
                "guest_name": self._resolve_guest_name(booking),
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

            # Log modification activity
            staff_name = await self._get_staff_name(staff_user)
            await self._log_activity(
                property_id=booking.property_id,
                staff_id=staff_user.id,
                staff_name=staff_name,
                activity_type="BOOKING_MODIFIED",
                description=f"Booking modified: {payload.reason}",
                booking_id=booking.id,
                extra_data={
                    "guest_name": self._resolve_guest_name(booking),
                    "changed_fields": payload.dict(exclude_none=True),
                    "reason": payload.reason,
                    "refund_due": float(refund_due) if refund_due > 0 else None,
                },
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
            raise BookingException(f"Room(s) not found: {', '.join(missing)}")

        rooms_needed = len(room_ids)
        adults_per_room = math.ceil(adults / rooms_needed)
        children_per_room = math.ceil(children / rooms_needed)

        insufficient = [
            room
            for room in rooms
            if room.max_adults < adults_per_room or room.max_children < children_per_room
        ]

        if insufficient:
            raise BookingException(
                f"Selected room(s) cannot accommodate {adults} adult(s) and "
                f"{children} child(ren) across {rooms_needed} room(s)."
            )

    # ─────────────────────── Walk-in Booking ─────────────────────────────

    async def create_walkin_booking(
        self, staff_user: User, payload
    ) -> dict:
        """Create a booking for a walk-in guest with contact info."""
        logger.info(
            f"[StaffOperationsService] Creating walk-in booking for property {payload.property_id}"
        )
        try:
            # 1. Verify staff-property assignment
            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(
                    staff_user, payload.property_id
                )

            # 2. Validate dates
            today = datetime.now(timezone.utc).date()
            if payload.check_in < today:
                raise InvalidDateException("Check-in date cannot be in the past.")
            if payload.check_in >= payload.check_out:
                raise InvalidDateException(
                    "Check-in date must be strictly before check-out date."
                )

            nights = (payload.check_out - payload.check_in).days

            # 3. Validate rooms
            rooms_needed = len(payload.room_ids)
            requested_rooms = await self.room_repo.get_by_ids_with_details(
                payload.room_ids
            )
            if len(requested_rooms) != rooms_needed:
                raise RoomsUnavailableError(
                    "Some rooms are invalid or do not exist."
                )
            if any(r.property_id != payload.property_id for r in requested_rooms):
                raise RoomsUnavailableError(
                    "Some rooms do not belong to the selected property."
                )

            # 4. Capacity check
            total_max_adults = sum(r.max_adults for r in requested_rooms)
            total_max_children = sum(r.max_children for r in requested_rooms)
            if payload.adults > total_max_adults or payload.children > total_max_children:
                raise RoomsUnavailableError(
                    "The selected room(s) cannot accommodate the total number of guests."
                )

            # 5. Soft lock + re-verify availability
            still_free_ids = await self.room_repo.lock_and_check_rooms(
                payload.room_ids, payload.check_in, payload.check_out
            )
            if len(still_free_ids) < rooms_needed:
                await self.db.rollback()
                raise RoomsUnavailableError(
                    "One or more rooms were just booked by another guest. "
                    "Please choose different rooms or dates."
                )

            # 6. Create BookingGuest record
            booking_guest = await self.booking_repo.create_booking_guest(
                full_name=payload.guest_full_name,
                email=payload.guest_email,
                phone=payload.guest_phone,
                nationality=payload.guest_nationality,
            )

            # 7. Calculate pricing
            subtotal = Decimal(
                str(sum(r.base_rate for r in requested_rooms) * nights)
            )
            active_offers = await self.offer_repo.get_active_offers(
                payload.property_id, payload.check_in, payload.check_out
            )
            special_offer_discount = Decimal(0)
            remaining = subtotal
            for offer in active_offers:
                offer_discount = min(
                    remaining
                    * Decimal(str(offer.discount_percentage))
                    / Decimal(100),
                    remaining,
                )
                special_offer_discount += offer_discount
                remaining -= offer_discount
            special_offer_discount = special_offer_discount.quantize(Decimal("0.01"))

            # 8. Apply coupon if provided
            coupon_code = None
            coupon_discount = Decimal("0.00")
            if payload.coupon_code:
                discount_code = await self.discount_code_repo.get_valid_code(
                    payload.property_id, payload.coupon_code
                )
                if discount_code is None:
                    raise BookingException("Invalid or expired discount code.")

                total_after_offers = subtotal - special_offer_discount
                if total_after_offers < discount_code.min_amount:
                    raise BookingException(
                        f"Minimum order amount of {discount_code.min_amount} not met."
                    )

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
                coupon_code = payload.coupon_code.strip().upper()
                await self.discount_code_repo.increment_used_count(discount_code.id)

            total_amount = subtotal - special_offer_discount - coupon_discount

            # 9. Determine payment status
            payment_method_str = payload.payment_method.upper()
            payment_method_enum = PaymentMethod(payment_method_str)
            amount_paid = Decimal(str(payload.amount_paid)) if payload.amount_paid else Decimal("0.00")
            advance_amount = Decimal(str(payload.advance_amount)) if payload.advance_amount else None

            # For PAY_ON_ARRIVAL, confirm immediately
            if payment_method_str == "PAY_ON_ARRIVAL":
                booking_status = MasterBookingStatus.CONFIRMED
                amount_due = total_amount - amount_paid
                payment_status = (
                    PaymentStatus.PAID
                    if amount_due <= Decimal("0")
                    else PaymentStatus.UNPAID
                    if amount_paid == Decimal("0")
                    else PaymentStatus.PARTIAL
                )
            else:
                booking_status = MasterBookingStatus.PENDING
                if payment_method_str == "ADVANCE" and advance_amount:
                    amount_due = total_amount - advance_amount
                    payment_status = (
                        PaymentStatus.PARTIAL
                        if amount_paid > Decimal("0")
                        else PaymentStatus.UNPAID
                    )
                else:
                    amount_due = total_amount - amount_paid
                    payment_status = (
                        PaymentStatus.PAID
                        if amount_due <= Decimal("0")
                        else PaymentStatus.UNPAID
                        if amount_paid == Decimal("0")
                        else PaymentStatus.PARTIAL
                    )

            if amount_due < Decimal("0"):
                amount_due = Decimal("0.00")

            # 10. Create booking record
            booking = await self.booking_repo.create_booking(
                guest_id=None,
                property_id=payload.property_id,
                room_ids=payload.room_ids,
                adults=payload.adults,
                children=payload.children,
                check_in=payload.check_in,
                check_out=payload.check_out,
                total_amount=total_amount,
                subtotal=subtotal,
                special_offer_discount=special_offer_discount,
                ref_number=self._generate_ref_number(),
                booking_type=BookingType.WALK_IN,
                booking_guest_id=booking_guest.id,
                payment_method=payment_method_enum,
                payment_status=payment_status,
                amount_paid=amount_paid,
                amount_due=amount_due,
                advance_amount=advance_amount,
                coupon_code=coupon_code,
                coupon_discount=coupon_discount,
                special_requests=payload.special_requests,
                status=MasterBookingStatus.CONFIRMED,
            )

            # Log walk-in booking activity
            staff_name = await self._get_staff_name(staff_user)
            await self._log_activity(
                property_id=payload.property_id,
                staff_id=staff_user.id,
                staff_name=staff_name,
                activity_type="WALKIN_BOOKING",
                description=f"Walk-in booking created for {payload.guest_full_name}",
                booking_id=booking.id,
                extra_data={
                    "guest_name": payload.guest_full_name,
                    "guest_email": payload.guest_email,
                    "room_names": [r.room_name for r in requested_rooms],
                    "total_amount": float(total_amount),
                    "amount_paid": float(amount_paid),
                },
            )

            await self.db.commit()

            # 11. Handle soft-lock / confirm
            if payment_method_str == "PAY_ON_ARRIVAL":
                # Already confirmed, clear soft-lock
                pass
            else:
                # Set soft-lock for PENDING bookings
                from app.config.settings_config import settings
                SOFT_LOCK_TTL_SECONDS = settings.SOFT_LOCK_TTL_SECONDS
                await self.redis.set(
                    f"booking:softlock:{booking.id}",
                    "pending",
                    ex=SOFT_LOCK_TTL_SECONDS,
                )

            # 12. Build response
            property_obj = await self.property_repo.get_by_id(payload.property_id)
            rooms_data = [
                {
                    "room_id": r.id,
                    "room_name": r.room_name,
                    "room_type": r.room_type.room_type_name if r.room_type else "",
                    "bed_type": r.bed_type.bed_name if r.bed_type else "",
                    "base_rate": float(r.base_rate),
                }
                for r in requested_rooms
            ]

            return {
                "booking_id": booking.id,
                "ref_number": booking.ref_number,
                "status": booking.status.value,
                "booking_type": BookingType.WALK_IN.value,
                "number_of_adults": payload.adults,
                "number_of_children": payload.children,
                "check_in": booking.checkin_date,
                "check_out": booking.checkout_date,
                "nights": nights,
                "payment_method": payment_method_str,
                "payment_status": payment_status.value,
                "amount_paid": float(amount_paid),
                "amount_due": float(amount_due),
                "advance_amount": float(advance_amount) if advance_amount else None,
                "total_amount": float(total_amount),
                "subtotal": float(subtotal),
                "coupon_code": coupon_code,
                "coupon_discount": float(coupon_discount),
                "special_requests": payload.special_requests,
                "property": {
                    "property_id": property_obj.id,
                    "name": property_obj.name,
                    "check_in_time": property_obj.check_in_time,
                    "check_out_time": property_obj.check_out_time,
                    "always_allow_check_in_out": property_obj.always_allow_check_in_out,
                },
                "rooms": rooms_data,
                "booking_guest": {
                    "booking_guest_id": booking_guest.id,
                    "full_name": booking_guest.full_name,
                    "email": booking_guest.email,
                    "phone": booking_guest.phone,
                    "nationality": booking_guest.nationality,
                },
                "created_at": booking.created_at,
            }

        except (
            RoomsUnavailableError,
            InvalidDateException,
            BookingException,
            PermissionException,
        ):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[StaffOperationsService] Error creating walk-in booking: {e}"
            )
            raise ServiceException(
                "Could not create walk-in booking. Please try again."
            )

    # ─────────────────────── Cancel Booking ──────────────────────────────

    async def cancel_booking(
        self, ref_number: str, staff_user: User, reason: str
    ) -> dict:
        """Staff can cancel any PENDING, CONFIRMED, or EXPIRED booking."""
        logger.info(
            f"[StaffOperationsService] Cancelling booking {ref_number} by staff {staff_user.id}"
        )
        try:
            # 1. Fetch booking with details
            booking = await self.staff_ops_repo.get_booking_by_ref_with_details(
                ref_number
            )
            if booking is None:
                raise BookingException("Booking not found")

            # 2. Verify staff-property assignment
            if staff_user.role != "admin":
                await self._verify_staff_property_assignment(
                    staff_user, booking.property_id
                )

            # 3. Atomic cancel transition
            snapshot = await self.booking_repo.try_cancel_booking(ref_number)
            if snapshot is None:
                current_status = (
                    booking.status.value
                    if hasattr(booking.status, "value")
                    else booking.status
                )
                raise BookingException(
                    f"Booking in status {current_status} cannot be cancelled. "
                    "Only PENDING, CONFIRMED, or EXPIRED bookings can be cancelled."
                )
            # 4. If guest has paid amount, set refund_due
            refund_due = Decimal("0.00")
            if booking.amount_paid > 0:
                refund_due = booking.amount_paid
                await self.staff_ops_repo.set_refund_due_on_cancel(
                    ref_number, refund_due
                )

            # 5. Reset room statuses to AVAILABLE
            staff_name = await self._get_staff_name(staff_user)
            room_ids = [br.room_unit_id for br in booking.booking_rooms]
            if room_ids:
                await self.staff_ops_repo.update_rooms_status(
                    room_ids, RoomStatus.AVAILABLE,
                    property_id=booking.property_id,
                    staff_id=staff_user.id,
                    staff_name=staff_name,
                )

            # 6. Clear Redis soft-lock if present
            await self.redis.delete(f"booking:softlock:{booking.id}")

            # 7. Write audit log
            before_snapshot = {
                "status": snapshot["status"],
                "total_amount": snapshot["total_amount"],
                "amount_paid": snapshot["amount_paid"],
            }
            after_snapshot = {
                "status": MasterBookingStatus.CANCELLED.value,
                "total_amount": snapshot["total_amount"],
                "amount_paid": snapshot["amount_paid"],
                "refund_due": str(refund_due),
            }
            self.db.add(
                BookingModificationLog(
                    booking_id=booking.id,
                    staff_id=staff_user.id,
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                    changed_fields="status",
                    reason=reason,
                )
            )

            # Log cancellation activity
            await self._log_activity(
                property_id=booking.property_id,
                staff_id=staff_user.id,
                staff_name=staff_name,
                activity_type="BOOKING_CANCELLED",
                description=f"Booking cancelled: {reason}",
                booking_id=booking.id,
                extra_data={
                    "guest_name": self._resolve_guest_name(booking),
                    "reason": reason,
                    "refund_due": float(refund_due) if refund_due > 0 else None,
                },
            )

            await self.db.commit()

            message = "Booking cancelled successfully."
            if refund_due > 0:
                message += f" Refund of {refund_due} is owed to the guest — process via payment gateway."

            return {
                "ref_number": ref_number,
                "status": MasterBookingStatus.CANCELLED.value,
                "refund_due": float(refund_due),
                "message": message,
            }

        except (BookingException, PermissionException):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[StaffOperationsService] Error cancelling booking {ref_number}: {e}"
            )
            raise ServiceException(
                "Could not cancel booking. Please try again."
            )
        
