from app.utils.exceptions import RoomNotFoundException
import uuid

from sqlalchemy import func, select, or_
from sqlalchemy.orm import joinedload,selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pms.models.rooms_model import BedType, Rooms, RoomType, RoomStatus
from app.utils.exceptions import (
    RepositoryException,
)
from app.utils.logging import LoggerFactory
import psycopg.errors
from datetime import date
from typing import Sequence, Optional
from app.modules.booking.models.booking_model import (
    Booking,
    BookingRoom,
    MasterBookingStatus,
)


logger = LoggerFactory.get_logger(__name__)


class RoomRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rooms(
        self, property_id: uuid.UUID, rooms_data: list[dict]
    ) -> list[dict]:
        logger.info(
            f"[RoomRepository] Initiating bulk transaction for {len(rooms_data)} rooms"
        )
        try:
            rooms = [
                Rooms(
                    id=room.get("id", uuid.uuid4()),
                    property_id=property_id,
                    room_type_id=room["room_type_id"],
                    bed_type_id=room["bed_type_id"],
                    floor_number=room["floor_number"],
                    room_name=room["room_name"],
                    max_adults=room["max_adults"],
                    max_children=room["max_children"],
                    base_rate=room["base_rate"],
                    status=room["status"],
                    cancellation_policy=room["cancellation_policy"],
                    cancellation_title=room["cancellation_title"],
                    cancellation_description=room["cancellation_description"],
                    photos=room["photos"],
                    system_amenity_ids=room["system_amenity_ids"],
                    custom_amenities=room["custom_amenities"],
                )
                for room in rooms_data
            ]
            self.db.add_all(rooms)
            await self.db.flush()

            room_ids = [room.id for room in rooms]

            await self.db.commit()

            stmt = (
                select(Rooms)
                .where(Rooms.id.in_(room_ids))
                .options(joinedload(Rooms.room_type), joinedload(Rooms.bed_type))
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except IntegrityError as e:
            await self.db.rollback()

            # Extract the underlying driver error (asyncpg)
            orig_err = getattr(e, "orig", None)

            if orig_err and hasattr(orig_err, "__cause__"):
                pg_exc = orig_err.__cause__

                if isinstance(pg_exc, psycopg.errors.UniqueViolation):
                    # Target unique index/constraints (e.g., uq_room_types_property_id_room_type_name or your rooms unique name index)
                    constraint_name = pg_exc.constraint_name or pg_exc.index_name
                    logger.warning(
                        f"[RoomRepository] Unique key or index conflict hit: {constraint_name}"
                    )
                    raise RepositoryException(
                        internal_detail=f"A room configuration or name collision occurred (Violated: {constraint_name}).",
                        status_code=400,
                    )

                elif isinstance(pg_exc, psycopg.errors.CheckViolation):
                    # Target check constraints (e.g., chk_room_types_default_property_consistency)
                    constraint_name = pg_exc.constraint_name
                    logger.warning(
                        f"[RoomRepository] Check constraint broken: {constraint_name}"
                    )
                    raise RepositoryException(
                        internal_detail=f"Data failed business logic checks. Ensure standard/default flags are valid (Violated: {constraint_name}).",
                        status_code=400,
                    )

                elif isinstance(pg_exc, psycopg.errors.ForeignKeyViolation):
                    logger.warning(
                        f"[RoomRepository] Foreign key link missing: {pg_exc.detail}"
                    )
                    raise RepositoryException(
                        internal_detail="The specified room type, bed type, or property ID does not exist.",
                        status_code=400,
                    )

            # Fallback for generic integrity issues (e.g. non-nullable failures)
            logger.error(f"[RoomRepository] Database consistency violation: {str(e)}")
            raise RepositoryException(
                f"Database consistency error during batch processing: {str(e)}"
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[RoomRepository] Unexpected bulk creation collapse: {str(e)}"
            )
            raise RepositoryException(f"Failed to batch create rooms: {str(e)}")

    async def get_existing_room_type_name(self, property_id: uuid.UUID, name: str):
        """check name collision"""
        logger.info("[RoomRepository] Validating room type name collision")
        try:
            stmt = select(RoomType).where(
                # Match either this specific property OR a global default (property_id is NULL)
                or_(
                    RoomType.property_id == property_id, RoomType.property_id.is_(None)
                ),
                func.lower(RoomType.room_type_name) == func.lower(name),
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                f"[RoomRepository] Unexpected error checking room type name collision: {str(e)}"
            )
            raise RepositoryException(
                f"Failed to check room type name collision: {str(e)}"
            )

    async def get_existing_bed_type_name(self, property_id: uuid.UUID, name: str):
        logger.info("[RoomRepository] validating bed type name collision")
        try:
            stmt = select(BedType).where(
                # Match either this specific property OR a global default (property_id is NULL)
                or_(BedType.property_id == property_id, BedType.property_id.is_(None)),
                func.lower(BedType.bed_name) == func.lower(name),
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"[RoomRepository] Unexpected error checking bed type name collision: {str(e)}"
            )
            raise RepositoryException(
                f"Failed to check bed type name collision: {str(e)}"
            )

    async def create_room_type(self, property_id: uuid.UUID, room_type_data: dict):
        try:
            room_type = RoomType(
                property_id=property_id,
                room_type_name=room_type_data["room_type_name"],
                is_default=False,
            )
            self.db.add(room_type)
            await self.db.commit()
            await self.db.refresh(room_type)
            return room_type
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[RoomRepository] Unexpected error creating room type: {str(e)}"
            )
            raise RepositoryException(f"Failed to create room type: {str(e)}")

    async def create_bed_type(self, property_id: uuid.UUID, bed_type_data: dict):
        try:
            bed_type = BedType(
                property_id=property_id,
                bed_name=bed_type_data["bed_name"],
                is_default=False,
            )
            self.db.add(bed_type)
            await self.db.commit()
            await self.db.refresh(bed_type)
            return bed_type
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[RoomRepository] Unexpected error creating bed type: {str(e)}"
            )
            raise RepositoryException(f"Failed to create bed type: {str(e)}")

    async def get_existing_room_names(
        self, property_id: uuid.UUID, room_names: list[str]
    ):

        logger.info(
            f"[RoomRepository] getting all the room names for the property {property_id} and room names {room_names}"
        )
        try:
            lower_room_names = [name.lower() for name in room_names]

            stmt = select(Rooms).where(
                Rooms.property_id == property_id,
                func.lower(Rooms.room_name).in_(lower_room_names),
            )

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"[RoomRepository] Unexpected error getting room names: {str(e)}"
            )
            raise RepositoryException(f"Failed to get room names: {str(e)}")

    async def get_all_rooms(self, property_id: uuid.UUID,status:Optional[str] =None,floor_number:Optional[int] = None, skip: int = 0, limit: int = 20) -> tuple[Sequence[Rooms], int]:
        """Get all rooms for a property, including room types and bed types."""
        logger.info(f"[RoomRepository] Getting all rooms for property {property_id}")
        try:
            stmt = (
                select(Rooms)
                .where(Rooms.property_id == property_id)
                .options(joinedload(Rooms.room_type), joinedload(Rooms.bed_type))
                .order_by(Rooms.created_at.desc())
            )
            
            total_count_stmt = (
                select(func.count())
                .select_from(Rooms)
                .where(Rooms.property_id == property_id)
            )

            if status is not None:
                stmt = stmt.where(Rooms.status == status)
                total_count_stmt = total_count_stmt.where(Rooms.status == status)
            
            if floor_number is not None:
                stmt = stmt.where(Rooms.floor_number == floor_number)
                total_count_stmt = total_count_stmt.where(Rooms.floor_number == floor_number)

            stmt = stmt.offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            rooms = result.scalars().all()

            total_result = await self.db.execute(total_count_stmt)
            total_count = total_result.scalar() or 0

            logger.info(
                f"[RoomRepository] Found {len(rooms)} rooms for property {property_id}"
            )
            return (rooms, total_count)
        except Exception as e:
            logger.error(f"[RoomRepository] Unexpected error getting rooms: {str(e)}")
            raise RepositoryException(f"Failed to get rooms: {str(e)}")

    async def get_all_room_types(self, property_id: uuid.UUID) -> Sequence[RoomType]:
        """Get all room types for a property."""
        logger.info(
            f"[RoomRepository] Getting all room types for property {property_id}"
        )
        try:
            stmt = (
                select(RoomType)
                .where(
                    or_(
                        RoomType.property_id == property_id,
                        RoomType.property_id.is_(None),
                    )
                )
                # Optional: Order by defaults first, then alphabetically by name
                .order_by(RoomType.is_default.desc(), RoomType.room_type_name.asc())
            )
            result = await self.db.execute(stmt)
            room_types = result.scalars().all()

            logger.info(
                f"[RoomRepository] Found {len(room_types)} total room types for property {property_id}"
            )
            return room_types
        except Exception as e:
            logger.error(
                f"[RoomRepository] Unexpected error getting room types: {str(e)}"
            )
            raise RepositoryException(f"Failed to get room types: {str(e)}")

    async def get_all_bed_types(self, property_id: uuid.UUID) -> Sequence[BedType]:
        """Get all bed types for a property."""
        logger.info(
            f"[RoomRepository] Getting all bed types for property {property_id}"
        )
        try:
            stmt = (
                select(BedType)
                .where(
                    or_(
                        BedType.property_id == property_id,
                        BedType.property_id.is_(None),
                    )
                )
                # Optional: Order by defaults first, then alphabetically by name
                .order_by(BedType.is_default.desc(), BedType.bed_name.asc())
            )
            result = await self.db.execute(stmt)
            bed_types = result.scalars().all()

            logger.info(
                f"[RoomRepository] Found {len(bed_types)} total bed types for property {property_id}"
            )
            return bed_types
        except Exception as e:
            logger.error(
                f"[RoomRepository] Unexpected error getting bed types: {str(e)}"
            )
            raise RepositoryException(f"Failed to get bed types: {str(e)}")

    async def delete_room(self, room_id: uuid.UUID):
        logger.info(f"[RoomRepository] Deleting room {room_id}")
        try:
            stmt = select(Rooms).where(Rooms.id == room_id)
            result = await self.db.execute(stmt)
            room = result.scalar_one_or_none()
            if not room:
                raise RoomNotFoundException("Room not found")
            await self.db.delete(room)
            await self.db.commit()
            logger.info(f"[RoomRepository] Room {room_id} deleted successfully")
            return room
        except RoomNotFoundException:
            raise
        except Exception as e:
            logger.error(f"[RoomRepository] Unexpected error deleting room: {str(e)}")
            raise RepositoryException(f"Failed to delete room: {str(e)}")

    async def get_room(self, room_id: uuid.UUID) -> Optional[Rooms]:
        """Get a single room by ID with eager loading."""
        logger.info(f"[RoomRepository] Getting room with ID {room_id}")
        try:
            stmt = (
                select(Rooms)
                .where(Rooms.id == room_id)
                .options(joinedload(Rooms.room_type), joinedload(Rooms.bed_type))
            )
            result = await self.db.execute(stmt)
            room = result.scalar_one_or_none()

            if room:
                logger.info(f"[RoomRepository] Room {room_id} found successfully")
            else:
                logger.info(f"[RoomRepository] Room with ID {room_id} not found")
            return room
        except Exception as e:
            logger.error(f"[RoomRepository] Unexpected error getting room: {str(e)}")
            raise RepositoryException(f"Failed to get room: {str(e)}")

    async def get_room_by_name(
        self,
        property_id: uuid.UUID,
        room_name: str,
        exclude_room_id: Optional[uuid.UUID] = None,
    ) -> Optional[Rooms]:
        """
        Checks if a room name already exists within a specific property.
        Allows excluding a specific room_id to prevent self-conflict on updates.
        """
        try:
            # 1. Scope query strictly to the current property and target room name
            stmt = select(Rooms).where(
                Rooms.property_id == property_id, Rooms.room_name == room_name
            )

            # 2. If an exclusion ID is provided, append the exclusion condition
            if exclude_room_id is not None:
                stmt = stmt.where(Rooms.id != exclude_room_id)

            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                f"[RoomRepository] Error checking room name uniqueness: {str(e)}",
                exc_info=True,
            )
            raise RepositoryException(
                f"Failed to check room name availability: {str(e)}"
            )

    async def update_room(self, room_id: uuid.UUID, payload: dict):
        logger.info(f"[RoomRepository] Updating room {room_id}")
        try:
            stmt = select(Rooms).where(Rooms.id == room_id)
            result = await self.db.execute(stmt)
            room = result.scalar_one_or_none()

            if not room:
                raise RoomNotFoundException("Room not found")

            # 1. Handle nested 'photos' safely if present
            if "photos" in payload and payload["photos"]:
                photos_data = payload["photos"]
                if "cover" in photos_data:
                    room.cover = photos_data["cover"]
                if "gallery" in photos_data:
                    room.gallery = photos_data["gallery"]

            # 2. Update all other attributes dynamically, avoiding 'photos'
            for key, value in payload.items():
                if key == "photos":
                    continue  # Skip to prevent overwriting room.cover/room.gallery

                if hasattr(room, key):
                    setattr(room, key, value)

            # 3. Save updates. (self.db.update does not exist; tracked changes flush automatically on commit)
            await self.db.commit()
            await self.db.refresh(
                room
            )  # Refresh ensures your returned object has fully accurate state

            logger.info(f"[RoomRepository] Room {room_id} updated successfully")
            return room

        except RoomNotFoundException:
            raise
        except Exception as e:
            await (
                self.db.rollback()
            )  # Crucial: clean up the transaction state on failure
            logger.error(
                f"[RoomRepository] Unexpected error updating room: {str(e)}",
                exc_info=True,
            )
            raise RepositoryException(f"Failed to update room: {str(e)}")

    async def get_available_rooms(
        self,
        property_ids: list[uuid.UUID],
        check_in: date,
        check_out: date,
    ) -> list[Rooms]:
        """
        Returns rooms belonging to the given properties that are:
        - not permanently blocked (MAINTENANCE / OUT_OF_SERVICE)
        - not already booked for any overlapping date range
        """
        logger.info("[RoomRepository] Getting available rooms for properties")
        if not property_ids:
            logger.info("[RoomRepository] No properties provided, returning empty list")
            return []

        try:
            # Rooms with an overlapping active booking for the requested dates
            overlapping_room_ids_subq = (
                select(BookingRoom.room_unit_id)
                .join(Booking, Booking.id == BookingRoom.booking_id)
                .where(
                    Booking.status.in_(
                        [
                            MasterBookingStatus.PENDING,
                            MasterBookingStatus.CONFIRMED,
                            MasterBookingStatus.CHECKED_IN,
                        ]
                    ),
                    Booking.checkin_date < check_out,  # overlap formula
                    Booking.checkout_date > check_in,  # overlap formula
                )
            )

            stmt = select(Rooms).where(
                Rooms.property_id.in_(property_ids),
                Rooms.status.notin_(
                    [RoomStatus.MAINTENANCE, RoomStatus.OUT_OF_SERVICE]
                ),
                Rooms.id.notin_(overlapping_room_ids_subq),
            )

            result = await self.db.execute(stmt)
            rooms = result.scalars().all()
            logger.info("returning list of available rooms")
            return rooms
        except Exception as e:
            logger.error("[RoomRepository] Error getting available rooms")
            raise RepositoryException(f"Failed to get available rooms: {str(e)}")

    
    async def get_available_rooms_for_property(
        self, property_id: uuid.UUID, check_in: date, check_out: date
    ) -> list[Rooms]:
        logger.info("[RoomRepository] Getting available rooms for property: %s", property_id)
    
        if not property_id:
            logger.info("[RoomRepository] No property ID provided, returning empty list")
            return []
        
        try:
            # 1. Define the subquery for overlapping bookings
            overlapping_room_ids_subq = (
                select(BookingRoom.room_unit_id)
                .join(Booking, Booking.id == BookingRoom.booking_id)
                .where(
                    Booking.status.in_(
                        [
                            MasterBookingStatus.PENDING,
                            MasterBookingStatus.CONFIRMED,
                            MasterBookingStatus.CHECKED_IN,
                        ]
                    ),
                    Booking.checkin_date < check_out,
                    Booking.checkout_date > check_in,
                )
                .scalar_subquery()  # Crucial for clean subquery compilation
            )
            
            # 2. Query available rooms that are not in the overlapping subquery
            stmt = select(Rooms).where(
                Rooms.property_id == property_id,
                Rooms.status == RoomStatus.AVAILABLE,  
                Rooms.id.not_in(overlapping_room_ids_subq),  
               ).options(
                selectinload(Rooms.room_type),
                selectinload(Rooms.bed_type),
                selectinload(Rooms.system_amenities)
            )
            
            # 3. Execute async query
            result = await self.db.execute(stmt)
            rooms = list(result.scalars().all())
            
            logger.info("[RoomRepository] Found %d available rooms", len(rooms))
            return rooms
            
        except Exception as e:
            logger.error("[RoomRepository] Error getting available rooms for property %s: %s", property_id, str(e))
            raise RepositoryException(f"Failed to get available rooms: {str(e)}") from e
            

    async def get_by_ids_with_details(self, room_ids: list[uuid.UUID]) -> list[Rooms]:
        logger.info("[RoomRepository] Getting rooms by IDs with details")
        if not room_ids:
            return []
        try:
            stmt = (
                select(Rooms)
                .where(Rooms.id.in_(room_ids))
                .options(joinedload(Rooms.room_type), joinedload(Rooms.bed_type))
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("[RoomRepository] Error getting rooms by IDs with details")
            raise RepositoryException(f"Failed to get rooms: {str(e)}")

    async def get_by_ids(self, room_ids: list[uuid.UUID]) -> list[Rooms]:
        logger.info("[RoomRepository] Getting rooms by IDs")
        if not room_ids:
            logger.info("[RoomRepository] No room IDs provided, returning empty list")
            return []
        try:
            stmt = select(Rooms).where(Rooms.id.in_(room_ids))
            result = await self.db.execute(stmt)
            rooms = result.scalars().all()
            logger.info("returning list of rooms")
            return rooms
        except Exception as e:
            logger.error("[RoomRepository] Error getting rooms by IDs")
            raise RepositoryException(f"Failed to get rooms by IDs: {str(e)}")


    async def lock_and_check_rooms(
        self,
        room_ids: list[uuid.UUID],
        check_in: date,
        check_out: date,
    ) -> list[uuid.UUID]:
        logger.info("[RoomRepository] Locking and checking rooms")
        if not room_ids:
            logger.info("[RoomRepository] No room IDs provided, returning empty list")
            return []

        try:
            result = await self.db.execute(
                select(Rooms.id).where(Rooms.id.in_(room_ids)).with_for_update()
            )
            locked_room_ids = result.scalars().all()

            overlapping_subq = (
                select(BookingRoom.room_unit_id)
                .join(Booking, Booking.id == BookingRoom.booking_id)
                .where(
                    Booking.status.in_([
                        MasterBookingStatus.PENDING,
                        MasterBookingStatus.CONFIRMED,
                        MasterBookingStatus.CHECKED_IN,
                    ]),
                    Booking.checkin_date < check_out,
                    Booking.checkout_date > check_in,
                    BookingRoom.room_unit_id.in_(locked_room_ids),
                )
            )
            result = await self.db.execute(overlapping_subq)
            already_booked = set(result.scalars().all())

            logger.info("returning list of available rooms")
            return [rid for rid in locked_room_ids if rid not in already_booked]

        except Exception as e:
            logger.error("[RoomRepository] Error locking and checking rooms")
            raise RepositoryException(f"Failed to lock and check rooms: {str(e)}")
