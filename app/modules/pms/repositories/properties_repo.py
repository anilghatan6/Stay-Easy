import uuid
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pms.models.properties_model import (
    Amenity,
    Property,
)
from app.utils.exceptions import (
    RepositoryException,
    PropertyNotFoundException,
    AmenityNotFoundException,
)
from app.utils.logging import LoggerFactory
from typing import Sequence

logger = LoggerFactory.get_logger(__name__)


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
            f"[PropertyRepository] Resolving amenities for property: {amenity_ids}"
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
