import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.modules.booking.models.booking_model import (
    Booking,
    BookingRoom,
    BookingGuest,
    MasterBookingStatus,
)
from app.modules.pms.models.rooms_model import Rooms, RoomStatus
from app.modules.pms.models.rooms_model import RoomType, BedType
from app.modules.pms.models.activity_log_model import PropertyActivityLog
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
        """Fetch booking with rooms, property, guest, booking_guest, and folios for staff operations."""
        logger.info(f"[StaffOperationsRepository] Fetching booking {ref_number} for staff")
        try:
            from app.modules.booking.models.folio_models import Folio

            stmt = (
                select(Booking)
                .options(
                    joinedload(Booking.guest),
                    joinedload(Booking.booking_guest),
                    joinedload(Booking.property),
                    selectinload(Booking.booking_rooms)
                    .joinedload(BookingRoom.room_unit)
                    .options(
                    joinedload(Rooms.room_type),
                    selectinload(Rooms.system_amenities),
                    joinedload(Rooms.bed_type),
                ),
                    selectinload(Booking.folios).selectinload(Folio.charges),
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
        self,
        room_ids: list[uuid.UUID],
        new_status: RoomStatus,
        property_id: Optional[uuid.UUID] = None,
        staff_id: Optional[uuid.UUID] = None,
        staff_name: Optional[str] = None,
        old_status: Optional[RoomStatus] = None,
    ) -> None:
        """Bulk update room status for all rooms in a booking. Auto-logs activity when context is provided."""
        logger.info(
            f"[StaffOperationsRepository] Updating {len(room_ids)} rooms to {new_status}"
        )
        try:
            # Fetch room names before update for logging
            rooms = []
            if property_id and staff_id and staff_name:
                result = await self.db.execute(
                    select(Rooms).where(Rooms.id.in_(room_ids))
                )
                rooms = list(result.scalars().all())

            await self.db.execute(
                update(Rooms)
                .where(Rooms.id.in_(room_ids))
                .values(status=new_status)
            )

            # Auto-log room status changes
            if property_id and staff_id and staff_name and rooms:
                for room in rooms:
                    self.db.add(
                        PropertyActivityLog(
                            property_id=property_id,
                            staff_id=staff_id,
                            staff_name=staff_name,
                            activity_type="ROOM_STATUS_CHANGE",
                            description=f"Room {room.room_name} status changed to {new_status.value}",
                            room_id=room.id,
                            extra_data={
                                "old_status": old_status.value if old_status else None,
                                "new_status": new_status.value,
                                "room_name": room.room_name,
                            },
                        )
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
            "payment_status": booking.payment_status.value
            if hasattr(booking.payment_status, "value")
            else booking.payment_status,
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

    async def set_refund_due_on_cancel(
        self, ref_number: str, amount_paid: Decimal
    ) -> None:
        """Set refund_due to amount_paid and clear amount_due on cancellation."""
        logger.info(
            f"[StaffOperationsRepository] Setting refund_due={amount_paid} on cancel for {ref_number}"
        )
        try:
            await self.db.execute(
                update(Booking)
                .where(Booking.ref_number == ref_number)
                .values(
                    refund_due=amount_paid,
                    amount_due=Decimal("0.00"),
                )
            )
        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to set refund_due for {ref_number}: {e}"
            )
            raise RepositoryException("Could not set refund due.")

    async def get_property_activity_logs(
        self,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        activity_types: Optional[list[str]] = None,
    ) -> tuple[list[PropertyActivityLog], int]:
        """Fetch paginated activity logs for a property, filtered by activity types."""
        logger.info(
            f"[StaffOperationsRepository] Fetching activity logs for property {property_id}"
        )
        try:
            conditions = [PropertyActivityLog.property_id == property_id]
            if activity_types:
                conditions.append(PropertyActivityLog.activity_type.in_(activity_types))

            count_result = await self.db.execute(
                select(PropertyActivityLog).where(*conditions)
            )
            total = len(count_result.scalars().all())

            stmt = (
                select(PropertyActivityLog)
                .where(*conditions)
                .order_by(PropertyActivityLog.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            logs = list(result.scalars().all())

            return logs, total

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch activity logs: {e}"
            )
            raise RepositoryException("Could not fetch activity logs.")

    async def get_expected_arrivals(
        self, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Booking], int]:
        """Fetch all bookings with check-in date today only (paginated)."""
        logger.info(
            f"[StaffOperationsRepository] Fetching arrivals for property {property_id}"
        )
        try:
            today = date.today()
            base_filter = [
                Booking.property_id == property_id,
                Booking.checkin_date == today,
                Booking.status.in_([
                    MasterBookingStatus.CONFIRMED,
                    MasterBookingStatus.PENDING,
                ]),
            ]

            count_result = await self.db.execute(
                select(func.count()).select_from(Booking).where(*base_filter)
            )
            total = count_result.scalar() or 0

            stmt = (
                select(Booking)
                .where(*base_filter)
                .options(
                    joinedload(Booking.guest),
                    joinedload(Booking.booking_guest),
                    joinedload(Booking.property),
                    selectinload(Booking.booking_rooms)
                    .joinedload(BookingRoom.room_unit)
                    .options(
                        joinedload(Rooms.room_type),
                        joinedload(Rooms.bed_type),
                    ),
                )
                .order_by(Booking.checkin_date.asc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return list(result.unique().scalars().all()), total

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch expected arrivals: {e}"
            )
            raise RepositoryException("Could not fetch expected arrivals.")

    async def get_occupied_bookings(
        self, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Booking], int]:
        """Fetch all occupied bookings (CHECKED_IN) with check-out date today only (paginated)."""
        logger.info(
            f"[StaffOperationsRepository] Fetching departures for property {property_id}"
        )
        try:
            today = date.today()
            base_filter = [
                Booking.property_id == property_id,
                Booking.checkout_date == today,
                Booking.status == MasterBookingStatus.CHECKED_IN,
            ]

            count_result = await self.db.execute(
                select(func.count()).select_from(Booking).where(*base_filter)
            )
            total = count_result.scalar() or 0

            stmt = (
                select(Booking)
                .where(*base_filter)
                .options(
                    joinedload(Booking.guest),
                    joinedload(Booking.booking_guest),
                    joinedload(Booking.property),
                    selectinload(Booking.booking_rooms)
                    .joinedload(BookingRoom.room_unit)
                    .options(
                        joinedload(Rooms.room_type),
                        joinedload(Rooms.bed_type),
                    ),
                )
                .order_by(Booking.checkout_date.asc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return list(result.unique().scalars().all()), total

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch occupied bookings: {e}"
            )
            raise RepositoryException("Could not fetch occupied bookings.")

    async def get_front_desk_summary(
        self, property_id: uuid.UUID, today: date
    ) -> dict:
        """Get summary counts for front desk dashboard."""
        logger.info(
            f"[StaffOperationsRepository] Fetching front desk summary for property {property_id}"
        )
        try:
            # Today's arrivals (CONFIRMED/PENDING with checkin_date=today)
            arrivals_result = await self.db.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.checkin_date == today,
                    Booking.status.in_([
                        MasterBookingStatus.CONFIRMED,
                        MasterBookingStatus.PENDING,
                    ]),
                )
            )
            todays_arrivals = arrivals_result.scalar() or 0

            # Today's departures (CHECKED_IN with checkout_date=today)
            departures_result = await self.db.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.checkout_date == today,
                    Booking.status == MasterBookingStatus.CHECKED_IN,
                )
            )
            todays_departures = departures_result.scalar() or 0

            # Today's checked in (status changed to CHECKED_IN today)
            checked_in_result = await self.db.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status == MasterBookingStatus.CHECKED_IN,
                    Booking.checked_in_at >= today,
                    Booking.checked_in_at < today + timedelta(days=1),
                )
            )
            todays_checked_in = checked_in_result.scalar() or 0

            # Today's checked out (status changed to CHECKED_OUT today)
            checked_out_result = await self.db.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status == MasterBookingStatus.CHECKED_OUT,
                    Booking.checked_out_at >= today,
                    Booking.checked_out_at < today + timedelta(days=1),
                )
            )
            todays_checked_out = checked_out_result.scalar() or 0

            # Total available rooms
            available_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(
                    Rooms.property_id == property_id,
                    Rooms.status == RoomStatus.AVAILABLE,
                )
            )
            total_available_rooms = available_result.scalar() or 0

            # Total rooms in property
            total_rooms_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(Rooms.property_id == property_id)
            )
            total_rooms = total_rooms_result.scalar() or 0

            # Dirty rooms count
            dirty_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(
                    Rooms.property_id == property_id,
                    Rooms.status == RoomStatus.DIRTY,
                )
            )
            dirty_rooms = dirty_result.scalar() or 0

            # Currently occupied rooms
            occupied_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(
                    Rooms.property_id == property_id,
                    Rooms.status == RoomStatus.OCCUPIED,
                )
            )
            occupied_rooms = occupied_result.scalar() or 0

            return {
                "todays_arrivals": todays_arrivals,
                "todays_departures": todays_departures,
                "todays_checked_in": todays_checked_in,
                "todays_checked_out": todays_checked_out,
                "total_rooms": total_rooms,
                "total_available_rooms": total_available_rooms,
                "dirty_rooms": dirty_rooms,
                "occupied_rooms": occupied_rooms,
            }

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch front desk summary: {e}"
            )
            raise RepositoryException("Could not fetch front desk summary.")

    async def get_room_calendar(
        self,
        property_id: uuid.UUID,
        start_date: date,
        end_date: date,
        floor_number: Optional[int] = None,
        room_status: Optional[RoomStatus] = None,
    ) -> dict:
        """Fetch room availability calendar: each room's status for each day in the range."""
        logger.info(
            f"[StaffOperationsRepository] Fetching room calendar for property {property_id} "
            f"from {start_date} to {end_date}"
        )
        try:
            # 1. Fetch all rooms for the property
            room_filters = [Rooms.property_id == property_id]
            if floor_number is not None:
                room_filters.append(Rooms.floor_number == floor_number)
            if room_status is not None:
                room_filters.append(Rooms.status == room_status)

            rooms_stmt = (
                select(Rooms)
                .where(*room_filters)
                .options(
                    joinedload(Rooms.room_type),
                    joinedload(Rooms.bed_type),
                )
                .order_by(Rooms.floor_number.asc(), Rooms.room_name.asc())
            )
            rooms_result = await self.db.execute(rooms_stmt)
            rooms = list(rooms_result.unique().scalars().all())

            if not rooms:
                return {
                    "rooms": [],
                    "start_date": start_date,
                    "end_date": end_date,
                }

            room_ids = [r.id for r in rooms]

            # 2. Fetch active bookings overlapping the date range
            booking_stmt = (
                select(Booking, BookingRoom.room_unit_id)
                .join(BookingRoom, Booking.id == BookingRoom.booking_id)
                .where(
                    BookingRoom.room_unit_id.in_(room_ids),
                    Booking.status.in_([
                        MasterBookingStatus.PENDING,
                        MasterBookingStatus.CONFIRMED,
                        MasterBookingStatus.CHECKED_IN,
                    ]),
                    Booking.checkin_date < end_date,
                    Booking.checkout_date > start_date,
                )
                .options(
                    joinedload(Booking.guest),
                    joinedload(Booking.booking_guest),
                )
            )
            booking_result = await self.db.execute(booking_stmt)
            booking_rows = booking_result.unique().all()

            # 3. Build a lookup: room_id -> list of (checkin, checkout, ref_number, guest_name)
            room_bookings: dict[uuid.UUID, list] = {}
            for booking, room_unit_id in booking_rows:
                guest_name = None
                if booking.guest:
                    guest_name = booking.guest.full_name
                elif booking.booking_guest:
                    guest_name = booking.booking_guest.full_name

                if room_unit_id not in room_bookings:
                    room_bookings[room_unit_id] = []
                room_bookings[room_unit_id].append({
                    "checkin": booking.checkin_date,
                    "checkout": booking.checkout_date,
                    "ref_number": booking.ref_number,
                    "guest_name": guest_name,
                })

            # 4. Build the calendar matrix
            num_days = (end_date - start_date).days
            calendar_rooms = []

            for room in rooms:
                days = []
                active_bookings = room_bookings.get(room.id, [])

                for day_offset in range(num_days):
                    current_date = start_date + timedelta(days=day_offset)

                    # Check if any booking overlaps this specific date
                    overlapping = None
                    for b in active_bookings:
                        if b["checkin"] <= current_date < b["checkout"]:
                            overlapping = b
                            break

                    if overlapping:
                        days.append({
                            "date": current_date,
                            "status": "BOOKED",
                            "booking_ref": overlapping["ref_number"],
                            "guest_name": overlapping["guest_name"],
                        })
                    else:
                        # Use the room's current status
                        days.append({
                            "date": current_date,
                            "status": room.status.value,
                            "booking_ref": None,
                            "guest_name": None,
                        })

                calendar_rooms.append({
                    "room_id": room.id,
                    "room_name": room.room_name,
                    "room_type": room.room_type.room_type_name if room.room_type else "",
                    "bed_type": room.bed_type.bed_name if room.bed_type else "",
                    "floor_number": room.floor_number,
                    "days": days,
                })

            return {
                "rooms": calendar_rooms,
                "start_date": start_date,
                "end_date": end_date,
            }

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch room calendar: {e}"
            )
            raise RepositoryException("Could not fetch room calendar.")

    async def get_checked_in_guests_by_property(
        self, property_id: uuid.UUID, skip: int, limit: int
    ) -> tuple[list[dict], int]:
        """Get paginated list of guests with CHECKED_IN bookings at a property."""
        logger.info(
            f"[StaffOperationsRepository] Fetching checked-in guests for property {property_id}"
        )
        try:
            base_filter = (
                Booking.property_id == property_id,
                Booking.status == MasterBookingStatus.CHECKED_IN,
            )

            count_result = await self.db.execute(
                select(func.count()).select_from(Booking)
                .where(*base_filter)
            )
            total = count_result.scalar() or 0

            result = await self.db.execute(
                select(
                    Booking.guest_id.label("guest_id"),
                    Booking.booking_guest_id.label("booking_guest_id"),
                    Booking.ref_number.label("ref_number"),
                    Booking.checkin_date.label("checkin_date"),
                    Booking.checkout_date.label("checkout_date"),
                )
                .where(*base_filter)
                .order_by(Booking.checkin_date.desc())
                .offset(skip)
                .limit(limit)
            )
            rows = result.all()

            guest_ids = [row.guest_id for row in rows if row.guest_id]
            booking_guest_ids = [row.booking_guest_id for row in rows if row.booking_guest_id]

            guest_map = {}
            if guest_ids:
                from app.modules.auth.models.guests_model import Guest
                guest_result = await self.db.execute(
                    select(Guest).where(Guest.id.in_(guest_ids))
                )
                for g in guest_result.scalars().all():
                    guest_map[g.id] = g

            booking_guest_map = {}
            if booking_guest_ids:
                bg_result = await self.db.execute(
                    select(BookingGuest).where(BookingGuest.id.in_(booking_guest_ids))
                )
                for bg in bg_result.scalars().all():
                    booking_guest_map[bg.id] = bg

            guests = []
            for row in rows:
                guest = guest_map.get(row.guest_id)
                booking_guest = booking_guest_map.get(row.booking_guest_id)
                guests.append({
                    "guest_id": row.guest_id,
                    "booking_guest_id": row.booking_guest_id,
                    "full_name": guest.full_name if guest else (booking_guest.full_name if booking_guest else "Unknown"),
                    "email": guest.email if guest else (booking_guest.email if booking_guest else ""),
                    "phone": guest.phone if guest else (booking_guest.phone if booking_guest else None),
                    "nationality": guest.nationality if guest else (booking_guest.nationality if booking_guest else None),
                    "ref_number": row.ref_number,
                    "checkin_date": row.checkin_date,
                    "checkout_date": row.checkout_date,
                })

            return guests, total

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch checked-in guests: {e}"
            )
            raise RepositoryException("Could not fetch checked-in guests.")

    async def get_bookings_by_guest_for_property(
        self, guest_id: uuid.UUID, property_id: uuid.UUID, skip: int, limit: int
    ) -> tuple[list, int]:
        """Get paginated bookings for a specific guest at a property, with folio info."""
        logger.info(
            f"[StaffOperationsRepository] Fetching bookings for guest {guest_id} at property {property_id}"
        )
        try:
            from app.modules.booking.models.folio_models import Folio

            base_filter = (
                Booking.guest_id == guest_id,
                Booking.property_id == property_id,
            )

            count_result = await self.db.execute(
                select(func.count(Booking.id))
                .select_from(Booking)
                .where(*base_filter)
            )
            total = count_result.scalar() or 0

            result = await self.db.execute(
                select(Booking)
                .options(
                    selectinload(Booking.booking_rooms)
                    .joinedload(BookingRoom.room_unit)
                    .options(
                        joinedload(Rooms.room_type),
                        joinedload(Rooms.bed_type),
                    ),
                    selectinload(Booking.folios),
                )
                .where(*base_filter)
                .order_by(Booking.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            bookings = result.unique().scalars().all()

            return bookings, total

        except SQLAlchemyError as e:
            logger.error(
                f"[StaffOperationsRepository] Failed to fetch guest bookings: {e}"
            )
            raise RepositoryException("Could not fetch guest bookings.")

        