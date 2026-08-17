import uuid
from sqlalchemy import func, select, or_, text
from sqlalchemy.orm import joinedload,selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pms.models.properties_model import (
    Amenity,
    Property,
)
from app.modules.pms.models import Tenant

from app.modules.booking.models import (
    MasterBookingStatus,
    Booking,
    BookingRoom
)
# from app.modules.pms.models.rooms_model import Rooms, RoomStatus
from app.utils.exceptions import (
    RepositoryException,
    PropertyNotFoundException,
    AmenityNotFoundException,
)
from app.utils.logging import LoggerFactory
from typing import Sequence

logger = LoggerFactory.get_logger(__name__)

RADIUS_TIERS_METERS = [5000, 15000, 50000]  # 5km, 15km, 50km
MIN_RESULTS_THRESHOLD = 1


class PropertyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_property_by_id(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Property | None:
        logger.info(f"[PropertyRepository] Getting property by id: {property_id}")
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id,
                    Property.tenant_id == tenant_id,
                )
            )
            property = result.scalar_one_or_none()
            return property
        except Exception as e:
            logger.error(f"[PropertyRepository] Error getting property by id: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def get_property_with_rooms(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Property | None:
        logger.info(f"[PropertyRepository] Getting property with rooms by id: {property_id}")
        try:
            stmt = (
                select(Property)
                .where(
                    Property.id == property_id,
                    Property.tenant_id == tenant_id,
                )
                .options(selectinload(Property.rooms))
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[PropertyRepository] Error getting property with rooms: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def update_property(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, update_data: dict
    ) -> Property:
        logger.info(f"[PropertyRepository] Updating property: {property_id}")
        try:
            property_obj = await self.get_property_by_id(property_id, tenant_id)
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            for field, value in update_data.items():
                if field == "photos" and isinstance(value, dict):
                    if property_obj.photos is None:
                        property_obj.photos = {}
                    for k, v in value.items():
                        property_obj.photos[k] = v
                else:
                    setattr(property_obj, field, value)

            await self.db.commit()
            await self.db.refresh(property_obj)
            return property_obj
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error updating property: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def get_by_id(self, property_id: uuid.UUID) -> Property | None:
        logger.info(f"[PropertyRepository] Getting specific property by id: {property_id}")
        try:
            stmt = (
            select(Property)
                .options(
                    joinedload(Property.tenant).joinedload(Tenant.owner)
                )
                .where(Property.id == property_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[PropertyRepository] Error getting property by id: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def create_property_full(
        self,
        tenant_id: uuid.UUID,
        property_data: dict,
    ) -> Property:
        """
        Creates a Property row from a fully-assembled flat dict (general info +
        location + localization + photos/amenities + optional brand visual).
        property_data['id'] is expected to already be a pre-generated UUID —
        set by the service BEFORE calling this, since image promotion needs
        the real property_id to exist before the row itself is inserted.
        """
        logger.info(f"[PropertyRepository] Creating full property for tenant: {tenant_id}")
        try:
            new_property = Property(
                tenant_id=tenant_id,
                **property_data,
            )
            self.db.add(new_property)
            await self.db.commit()
            await self.db.refresh(new_property)
            return new_property

        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Integrity error creating property: {str(e)}")
            raise RepositoryException(
                internal_detail=f"Database consistency failure: {str(e)}"
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error creating property: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def get_property_by_name(
        self, property_name: str, tenant_id: uuid.UUID
    ) -> Property | None:
        logger.info(f"[PropertyRepository] Getting property by name: {property_name}")
        try:
            result = await self.db.execute(
                select(Property).where(
                    func.lower(Property.name) == property_name.lower(),
                    Property.tenant_id == tenant_id,
                )
            )
            property = result.scalars().one_or_none()
            return property
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Error getting property by name: {str(e)}"
            )
            raise RepositoryException(internal_detail=str(e))

    async def create_general_information(
        self, property_data: dict, tenant_id: uuid.UUID
    ) -> dict:
        logger.info("[PropertyRepository] Creating general information")
        try:
            property_data.setdefault("system_amenity_ids", [])
            property_data.setdefault("custom_amenities", [])
            property_data.setdefault("photos", {"cover": None, "gallery": []})
            new_property = Property(tenant_id=tenant_id, **property_data)
            self.db.add(new_property)
            await self.db.commit()
            await self.db.refresh(new_property)

            return {
                "id": new_property.id,
                "name": new_property.name,
                "type": new_property.type,
                "description": new_property.description,
                "total_rooms": new_property.total_rooms,
                "year_built": new_property.year_built,
                "number_of_floors": new_property.number_of_floors,
                "phone_number": new_property.phone_number,
                "email": new_property.email,
                "created_at": new_property.created_at,
                "updated_at": new_property.updated_at,
            }
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(
                f"[PropertyRepository] Integrity Error creating general information: {str(e)}"
            )
            raise RepositoryException(
                internal_detail=f"Database consistency failure: {str(e)}"
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PropertyRepository] Error creating general information: {str(e)}"
            )
            raise RepositoryException(internal_detail=str(e))

    async def create_location(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, location_data: dict
    ) -> Property:
        logger.info(
            f"[PropertyRepository] Updating location for property: {property_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            for key, value in location_data.items():
                setattr(property_obj, key, value)

            await self.db.commit()
            await self.db.refresh(property_obj)
            return property_obj
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error updating location: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def validate_amenities(
        self,
        system_amenity_ids: list[uuid.UUID],
        custom_amenities: list[dict],
    ) -> set[str]:
        """
        Validates system amenity IDs and returns a set of system amenity names (lowercase).
        Raises:
            AmenityNotFoundException: if any provided ID does not exist in the DB.
        """
        if not system_amenity_ids:
            return set()

        logger.info(
            f"[PropertyRepository] Validating {len(system_amenity_ids)} system amenity IDs"
        )
        try:
            stmt = select(Amenity.id, Amenity.name).where(
                Amenity.id.in_(system_amenity_ids)
            )
            result = await self.db.execute(stmt)
            rows = result.all()  # list of (id, name) tuples

            found_ids = {row.id for row in rows}
            missing_ids = set(system_amenity_ids) - found_ids

            if missing_ids:
                missing_str = ", ".join(str(mid) for mid in missing_ids)
                logger.error(
                    f"[PropertyRepository] Invalid system amenity IDs: {missing_str}"
                )
                raise AmenityNotFoundException(
                    user_message="One or more provided default amenities are not found.",
                    internal_detail=f"Invalid system amenity IDs: {missing_str}",
                )

            system_names = {row.name.lower() for row in rows}
            return system_names

        except AmenityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"[PropertyRepository] Error validating amenities: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def create_photos_and_amenities(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, data: dict
    ) -> Property:
        logger.info(
            f"[PropertyRepository] creating photos and amenities for property: {property_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            if "photos" in data:
                property_obj.photos = data["photos"]

            if "amenities" in data:
                amenities = data["amenities"]
                if "system_amenity_ids" in amenities:
                    property_obj.system_amenity_ids = amenities["system_amenity_ids"]
                if "custom_amenities" in amenities:
                    property_obj.custom_amenities = amenities["custom_amenities"]

            await self.db.commit()
            await self.db.refresh(property_obj)
            return property_obj
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PropertyRepository] Error creating photos and amenities: {str(e)}"
            )
            raise RepositoryException(internal_detail=str(e))

    async def create_localization(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, localization_data: dict
    ) -> Property:
        logger.info(
            f"[PropertyRepository] Updating localization for property: {property_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            for key, value in localization_data.items():
                setattr(property_obj, key, value)

            await self.db.commit()
            await self.db.refresh(property_obj)
            return property_obj
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error updating localization: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def create_brand_visual(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, brand_data: dict
    ) -> Property:
        logger.info(
            f"[PropertyRepository] Updating brand visual for property: {property_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            for key, value in brand_data.items():
                setattr(property_obj, key, value)

            await self.db.commit()
            await self.db.refresh(property_obj)
            return property_obj
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error updating brand visual: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def get_properties_by_tenant(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 10
    ) -> tuple[Sequence[Property], int]:
        """
        Fetches a paginated list of properties and the total count for a tenant.
        """
        try:
            # Query to fetch the list of properties
            query = (
                select(Property)
                .where(Property.tenant_id == tenant_id)
                .order_by(Property.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(query)
            properties = result.scalars().all()

            # Query to fetch the total count for pagination metadata
            count_query = (
                select(func.count())
                .select_from(Property)
                .where(Property.tenant_id == tenant_id)
            )
            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar_one()

            return properties, total_count
        except Exception as e:
            logger.error(f"[PropertyRepository] Error fetching properties: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def get_all_system_amenities(self) -> Sequence[Amenity]:
        """
        Fetches the complete catalog of master system amenities from the database.
        """
        logger.info(
            "[PropertyRepository] Fetching full master system amenities catalog"
        )
        try:
            stmt = select(Amenity).order_by(Amenity.name.asc())
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Failed to fetch system amenities: {str(e)}"
            )
            raise RepositoryException(f"Failed to load system master options: {str(e)}")

    async def resolve_amenities_for_property(
        self, amenity_ids: list[uuid.UUID]
    ) -> Sequence[Amenity]:
        """
        Fetches the full Amenity records belonging specifically to this property's array.
        """
        logger.info(
            "[PropertyRepository] Resolving amenities for property"
        )
        try:
            if not amenity_ids:
                return []

            stmt = select(Amenity).where(Amenity.id.in_(amenity_ids))
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Failed to resolve amenities for property: {str(e)}"
            )
            raise RepositoryException(f"Failed to load system master options: {str(e)}")

    async def delete_property(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        logger.info(
            f"[PropertyRepository] Deleting property: {property_id} for tenant: {tenant_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            await self.db.delete(property_obj)
            await self.db.commit()
            logger.info(
                f"[PropertyRepository] Deleted property: {property_id} for tenant: {tenant_id}"
            )
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[PropertyRepository] Error deleting property: {str(e)}")
            raise RepositoryException(internal_detail=str(e))

    async def search_by_destination(
        self, query: str, threshold: float = 0.2
    ) -> list[tuple[Property, float]]:
        """
        Fuzzy destination search using pg_trgm similarity.
        Returns list of (Property, score) tuples, ordered by best match first.
        """
        logger.info(f"[PropertyRepository] Searching by destination: {query}")
        await self.db.execute(
            text("SELECT set_config('pg_trgm.similarity_threshold', :t, false)"),
            {"t": "0.2"},  # Note: PostgreSQL set_config expects the value as a string
        )
        try:
            score = func.greatest(
                func.similarity(Property.name, query),
                func.similarity(Property.country, query),
                func.similarity(Property.state, query),
                func.similarity(Property.city, query),
                func.similarity(Property.address, query),
                func.similarity(Property.type, query),
            ).label("score")

            stmt = (
                select(Property, score)
                .where(
                    or_(
                        Property.name.op("%")(query),
                        Property.country.op("%")(query),
                        Property.state.op("%")(query),
                        Property.city.op("%")(query),
                        Property.address.op("%")(query),
                        Property.type.op("%")(query),
                    ),
                    Property.is_active,
                )
                .order_by(score.desc())
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            logger.info("returning tuple of property and score")
            return [(row[0], row[1]) for row in rows]

        except Exception as e:
            logger.error(
                f"[PropertyRepository] Error searching by destination: {str(e)}"
            )
            raise RepositoryException(
                internal_detail=f"Failed to search by destination: {str(e)}"
            )

    async def get_by_ids(self, property_ids: list[uuid.UUID]) -> list[Property]:
        logger.info(f"[PropertyRepository] Getting properties by ids: {property_ids}")
        try:
            if not property_ids:
                return []
            stmt = select(Property).where(Property.id.in_(property_ids))
            result = await self.db.execute(stmt)
            logger.info("returning the list of properties")
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Error getting properties by ids: {str(e)}"
            )
            raise RepositoryException(
                internal_detail=f"Failed to get properties: {str(e)}"
            )

    async def get_amenities_by_ids(self, amenity_ids: list[uuid.UUID]) -> list[Amenity]:
        logger.info("[PropertyRepository] getting amenities by ids")
        if not amenity_ids:
            return []
        try:
            stmt = select(Amenity).where(Amenity.id.in_(amenity_ids))
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Error getting amenities by ids: {str(e)}"
            )
            raise RepositoryException(
                internal_detail=f"Failed to get amenities: {str(e)}"
            )

    async def toggle_property_activation(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> bool:
        logger.info(
            f"[PropertyRepository] Toggling activation for property: {property_id}"
        )
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id, Property.tenant_id == tenant_id
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            property_obj.is_active = not property_obj.is_active
            new_status = property_obj.is_active

            await self.db.commit()
            await self.db.refresh(property_obj)
            return new_status
        except PropertyNotFoundException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PropertyRepository] Error toggling property activation: {str(e)}"
            )
            raise RepositoryException(internal_detail=str(e))

    async def get_number_of_floors(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> int | None:
        logger.info("[PropertyRepository] Getting the number of floors")
        try:
            result = await self.db.execute(
                select(Property).where(
                    Property.id == property_id,
                    Property.tenant_id == tenant_id,
                )
            )
            property_obj = result.scalar_one_or_none()
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")
            return property_obj.number_of_floors
        except PropertyNotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"[PropertyRepository] Error getting number of floors: {str(e)}"
            )
            raise RepositoryException(internal_detail=str(e))

    async def get_nearby_properties(
        self, lat: float, lon: float, limit: int 
    ) -> list[tuple[list, int]]:
        """
        Progressively expands search radius (5km -> 15km -> 50km) until
        enough results are found. Returns (rows, radius_used_in_meters).
        """
        logger.info(
            f"[PropertyRepository] Getting nearby properties for lat: {lat}, lon: {lon}"
        )
        rows = []
        radius_used = RADIUS_TIERS_METERS[-1]

        try:
            for radius_m in RADIUS_TIERS_METERS:
                logger.info(f"[PropertyRepository] Trying radius {radius_m}m")
                stmt = text("""
                    SELECT
                        p.id, p.name, p.type, p.country, p.state, p.city, p.address, p.currency,
                        p.photos ->> 'cover' AS cover_photo,
                        ST_Distance(
                            p.geo_location,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                        ) AS distance_m,
                        lowest_rate.min_base_rate
                    FROM properties p
                    LEFT JOIN LATERAL (
                        SELECT MIN(r.base_rate) AS min_base_rate
                        FROM rooms r
                        WHERE r.property_id = p.id
                          AND r.status NOT IN ('MAINTENANCE', 'OUT_OF_SERVICE')
                          AND r.id NOT IN (
                              SELECT br.room_unit_id
                              FROM booking_rooms br
                              JOIN bookings b ON b.id = br.booking_id
                              WHERE b.status IN ('PENDING', 'CONFIRMED', 'CHECKED_IN')
                                AND b.checkin_date < (CURRENT_DATE + INTERVAL '1 day')
                                AND b.checkout_date > CURRENT_DATE
                          )
                    ) lowest_rate ON true
                    WHERE p.is_active = true
                      AND p.geo_location IS NOT NULL
                      AND ST_DWithin(
                          p.geo_location,
                          ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                          :radius
                      )
                    ORDER BY distance_m ASC
                    LIMIT :limit
                """)
                result = await self.db.execute(
                    stmt,
                    {
                        "lng": lon,
                        "lat": lat,
                        "radius": radius_m,
                        "limit": limit,
                    },
                )
                rows = result.fetchall()
                radius_used = radius_m

                if len(rows) >= MIN_RESULTS_THRESHOLD:
                    break

            logger.info(
                f"[PropertyRepository] Found {len(rows)} properties within {radius_used}m"
            )
            return rows, radius_used

        except SQLAlchemyError as e:
            logger.error(f"[PropertyRepository] Failed to find nearby properties: {e}")
            raise RepositoryException(
                internal_detail="Could not search for nearby properties. Please try again."
            )

    async def get_property_bookings(self, property_id, tenant_id, skip:int, limit:int):
        logger.info("[PropertyRepository] getting property bookings")
        try:
            excludes_booking_status = {
                MasterBookingStatus.EXPIRED,
                MasterBookingStatus.PENDING,

            }

            count_stmt = (
            select(func.count())
            .select_from(Booking)
            .where(Booking.property_id == property_id, Booking.status.notin_(excludes_booking_status))
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

         
            stmt = (
                select(Booking)
                .where(Booking.property_id == property_id, Booking.status.notin_(excludes_booking_status))
                .options(
                    joinedload(Booking.guest), # Eagerly joins the single Guest row
                    selectinload(Booking.booking_rooms)  # Slices mapping row collections efficiently
                .joinedload(BookingRoom.room_unit) # Joins exact Rooms table
                )
                .order_by(Booking.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            bookings = result.scalars().all()
            logger.info("[PropertyRepository] Successfully getting the booking information")
            return bookings, total
        
        except Exception as e:
            logger.error(f"[PropertyRepository] Error getting property bookings: {str(e)}")
            raise RepositoryException(internal_detail=str(e))


        
        