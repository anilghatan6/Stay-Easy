import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, update,delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.modules.booking.models.booking_model import (
    Booking,
    BookingRoom,
    MasterBookingStatus,
)
from app.modules.pms.models.rooms_model import Rooms, RoomStatus
from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.modules.auth.models.users_model import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory
from app.modules.booking.models.booking_model import PaymentStatus
from app.modules.booking.models.booking_modification_log import BookingModificationLog
logger = LoggerFactory.get_logger(__name__)


class StaffOperationsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_staff_by_email(self, email: str) -> Staff | None:
        """Find the Staff record matching a user's email."""
        logger.info(f"[StaffOperationsRepository] Finding staff by email")
        try:
            result = await self.db.execute(
                select(Staff).where(Staff.email == email)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[StaffOperationsRepository] Failed to find staff by email: {e}")
            raise RepositoryException("Could not verify staff assignment.")

    async def is_staff_assigned_to_property(
        self, staff_id: uuid.UUID, property_id: uuid.UUID
    ) -> bool:
        """Check if a staff member is assigned to a specific property."""
        logger.info(f"[StaffOperationsRepository] Checking staff-property assignment")
        try:
            result = await self.db.execute(
                select(StaffProperty).where(
                    StaffProperty.staff_id == staff_id,
                    StaffProperty.property_id == property_id,
                )
            )
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"[StaffOperationsRepository] Failed to check assignment: {e}")
            raise RepositoryException("Could not verify staff assignment.")

    async def get_booking_by_ref_with_details(self, ref_number: str) -> Booking | None:
        """Fetch booking with rooms, property, and guest for staff operations."""
        logger.info(f"[StaffOperationsRepository] Fetching booking {ref_number} for staff")
        try:
            stmt = (
                select(Booking)
                .options(
                    joinedload(Booking.guest),
                    joinedload(Booking.property),
                    selectinload(Booking.booking_rooms)
                    .joinedload(BookingRoom.room_unit)
                    .options(
                    joinedload(Rooms.room_type),
                    # Preloads the system_amenities relationship on the Rooms model
                    selectinload(Rooms.system_amenities),
                    joinedload(Rooms.bed_type),
                )
                )
                .where(Booking.ref_number == ref_number)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch booking {ref_number}: {e}"
            )
            raise RepositoryException("Could not fetch booking details.")

    async def try_check_in_booking(self, ref_number: str) -> Booking | None:
        """
        Atomically transitions booking from CONFIRMED to CHECKED_IN.
        Returns None if booking is not CONFIRMED.
        """
        logger.info(f"[StaffOperationsRepository] Checking in booking {ref_number}")
        try:
            result = await self.db.execute(
                select(Booking)
                .where(
                    Booking.ref_number == ref_number,
                    Booking.status == MasterBookingStatus.CONFIRMED,
                )
                .with_for_update()
            )
            booking = result.scalar_one_or_none()

            if booking is None:
                return None

            booking.status = MasterBookingStatus.CHECKED_IN
            booking.checked_in_at = datetime.now(timezone.utc)
            return booking

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to check in {ref_number}: {e}"
            )
            raise RepositoryException("Could not check in booking.")

    async def try_check_out_booking(self, ref_number: str) -> Booking | None:
        """
        Atomically transitions booking from CHECKED_IN to CHECKED_OUT.
        Returns None if booking is not CHECKED_IN.
        """
        logger.info(f"[StaffOperationsRepository] Checking out booking {ref_number}")
        try:
            result = await self.db.execute(
                select(Booking)
                .where(
                    Booking.ref_number == ref_number,
                    Booking.status == MasterBookingStatus.CHECKED_IN,
                )
                .with_for_update()
            )
            booking = result.scalar_one_or_none()

            if booking is None:
                return None

            booking.status = MasterBookingStatus.CHECKED_OUT
            booking.checked_out_at = datetime.now(timezone.utc)
            return booking

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to check out {ref_number}: {e}"
            )
            raise RepositoryException("Could not check out booking.")

    async def update_rooms_status(
        self, room_ids: list[uuid.UUID], new_status: RoomStatus
    ) -> None:
        """Bulk update room status for all rooms in a booking."""
        logger.info(
            f"[StaffOperationsRepository] Updating {len(room_ids)} rooms to {new_status}"
        )
        try:
            await self.db.execute(
                update(Rooms)
                .where(Rooms.id.in_(room_ids))
                .values(status=new_status)
            )
        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to update room statuses: {e}"
            )
            raise RepositoryException("Could not update room statuses.")

        
    async def apply_booking_modification(
        self,
        booking: Booking,
        staff_id: uuid.UUID,
        checkin_date: date,
        checkout_date: date,
        new_room_ids: Optional[list[uuid.UUID]],
        number_of_adults: Optional[int],
        number_of_children: Optional[int],
        special_requests: Optional[str],
        subtotal: Decimal,
        total_amount: Decimal,
        amount_due: Decimal,
        refund_due: Decimal,
        payment_status: PaymentStatus,
        reason: Optional[str] = None,
    ) -> Booking:
        # --- snapshot BEFORE state for the audit log ---
        before_snapshot = {
            "checkin_date": booking.checkin_date.isoformat(),
            "checkout_date": booking.checkout_date.isoformat(),
            "room_unit_ids": [str(br.room_unit_id) for br in booking.booking_rooms],
            "number_of_adults": booking.number_of_adults,
            "number_of_children": booking.number_of_children,
            "total_amount": str(booking.total_amount),
            "amount_paid": str(booking.amount_paid),
            "amount_due": str(booking.amount_due),
            "payment_status": booking.payment_status.value,
        }

        old_room_ids = [br.room_unit_id for br in booking.booking_rooms]
        rooms_changed = new_room_ids is not None and set(new_room_ids) != set(old_room_ids)

        # --- swap booking_rooms if rooms changed ---
        if rooms_changed:
            # free the old rooms (only meaningful if they were OCCUPIED, e.g. checked-in extension edge case;
            # for PENDING/CONFIRMED bookings they're likely already AVAILABLE, this is a safe no-op then)
            if old_room_ids:
                await self.db.execute(
                    update(Rooms)
                    .where(Rooms.id.in_(old_room_ids))
                    .values(status=RoomStatus.AVAILABLE)
                )

            await self.db.execute(
                delete(BookingRoom).where(BookingRoom.booking_id == booking.id)
            )
            self.db.add_all(
                [
                    BookingRoom(booking_id=booking.id, room_unit_id=rid)
                    for rid in new_room_ids
                ]
            )

            # if the booking is currently CHECKED_IN, the new rooms take over OCCUPIED status
            if booking.status == MasterBookingStatus.CHECKED_IN:
                await self.db.execute(
                    update(Rooms)
                    .where(Rooms.id.in_(new_room_ids))
                    .values(status=RoomStatus.OCCUPIED)
                )
            # if PENDING/CONFIRMED, leave new rooms' status as-is — they only become OCCUPIED at actual check-in

        # --- update the booking row itself ---
        update_values = {
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "subtotal": subtotal,
            "total_amount": total_amount,
            "amount_due": amount_due,
            "refund_due": refund_due,
            "payment_status": payment_status,
        }
        if number_of_adults is not None:
            update_values["number_of_adults"] = number_of_adults
        if number_of_children is not None:
            update_values["number_of_children"] = number_of_children
        if special_requests is not None:
            update_values["special_requests"] = special_requests

        await self.db.execute(
            update(Booking).where(Booking.id == booking.id).values(**update_values)
        )

        # --- write the audit log entry ---
        after_snapshot = {
            "checkin_date": checkin_date.isoformat(),
            "checkout_date": checkout_date.isoformat(),
            "room_unit_ids": [str(rid) for rid in (new_room_ids or old_room_ids)],
            "number_of_adults": number_of_adults if number_of_adults is not None else booking.number_of_adults,
            "number_of_children": number_of_children if number_of_children is not None else booking.number_of_children,
            "total_amount": str(total_amount),
            "amount_paid": str(booking.amount_paid),
            "amount_due": str(amount_due),
            "payment_status": payment_status.value,
        }

        changed = [
            k for k in before_snapshot
            if k in after_snapshot and str(before_snapshot[k]) != str(after_snapshot[k])
        ]

        self.db.add(
            BookingModificationLog(
                booking_id=booking.id,
                staff_id=staff_id,
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                changed_fields=", ".join(changed) if changed else "none",
                reason=reason,
            )
        )

        await self.db.flush()

        # re-fetch fresh with relationships loaded for the response
        result = await self.db.execute(
            select(Booking)
            .where(Booking.id == booking.id)
            .options(
                selectinload(Booking.booking_rooms).selectinload(BookingRoom.room_unit),
                selectinload(Booking.guest),
                selectinload(Booking.property),
            )
        )
        return result.scalar_one()



    async def check_rooms_available(
        self,
        room_ids: list[uuid.UUID],
        checkin_date: date,
        checkout_date: date,
        exclude_booking_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Returns the subset of room_ids that are ALREADY booked (i.e. conflicts).
        Empty list means all requested rooms are free for this range."""
        result = await self.db.execute(
            select(BookingRoom.room_unit_id)
            .join(Booking, Booking.id == BookingRoom.booking_id)
            .where(
                BookingRoom.room_unit_id.in_(room_ids),
                Booking.id != exclude_booking_id,
                Booking.status.in_([
                    MasterBookingStatus.PENDING,
                    MasterBookingStatus.CONFIRMED,
                    MasterBookingStatus.CHECKED_IN,
                ]),
                # standard overlap check: existing.checkin < new.checkout AND existing.checkout > new.checkin
                Booking.checkin_date < checkout_date,
                Booking.checkout_date > checkin_date,
            )
        )
        return list(result.scalars().all())

    async def get_rooms_by_ids(self, room_ids: list[uuid.UUID]) -> list[Rooms]:
        result = await self.db.execute(
            select(Rooms).where(Rooms.id.in_(room_ids))
        )
        return list(result.scalars().all())

        