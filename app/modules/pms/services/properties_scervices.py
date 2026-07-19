import uuid

from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.schemas.properties_schemas import (
    GeneralPropertyInfo,
    GeneralPropertyInfoResponse,
    Location,
    LocationResponse,
    PropertyPhotosAndAmenities,
    PropertyPhotosAndAmenitiesResponse,
    Propertylocalization,
    PropertylocalizationResponse,
    BrandVisual,
    BrandVisualResponse,
    PropertyResponse,
    TenantPropertiesListResponse,
    SystemAmenityResponse,
    SystemAmenitiesListResponse,
)
from app.utils.exceptions import (
    PropertyAlreadyExistsException,
    PropertyNotFoundException,
    RepositoryException,
    ServiceException,
    AmenityNotFoundException,
    ResourceConflictException,
    ImageStorageException,
)

from app.modules.pms.services.image_services import ImageService

from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class PropertyService:
    def __init__(self, property_repo: PropertyRepository, image_service: ImageService):
        self.property_repo = property_repo
        self.image_service = image_service

    async def create_general_information(
        self, payload: GeneralPropertyInfo, tenant_id: uuid.UUID
    ) -> GeneralPropertyInfoResponse:
        logger.info("[PropertyService] creating general information about the property")
        payload_dict = payload.model_dump()
        try:
            property_obj = await self.property_repo.get_property_by_name(
                payload_dict["name"], tenant_id
            )
            if property_obj:
                logger.warning(
                    f"Property with name {payload_dict['name']} already exists"
                )
                raise PropertyAlreadyExistsException(
                    f"Property with name {payload_dict['name']} already exists"
                )

            response = await self.property_repo.create_general_information(
                payload_dict, tenant_id
            )

            return GeneralPropertyInfoResponse.model_validate(response)

        except (PropertyAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(
                f"[PropertyService] Error creating general information: {str(e)}"
            )
            raise ServiceException(
                internal_detail=f"Failed to create general information of property :{str(e)}"
            )

    async def create_location(
        self, property_id: uuid.UUID, payload: Location, tenant_id: uuid.UUID
    ) -> LocationResponse:
        logger.info(f"[PropertyService] creating location for property {property_id}")
        payload_dict = payload.model_dump()
        try:
            property_obj = await self.property_repo.create_location(
                property_id, tenant_id, payload_dict
            )
            return LocationResponse.model_validate(property_obj)
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error updating location: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to update location for property: {str(e)}"
            )

    async def create_photos_and_amenities(
        self,
        property_id: uuid.UUID,
        payload: PropertyPhotosAndAmenities,
        tenant_id: uuid.UUID,
    ) -> PropertyPhotosAndAmenitiesResponse:
        logger.info(
            f"[PropertyService] creating photos and amenities for property {property_id}"
        )
        payload_dict = payload.model_dump()

        try:
            amenities_data = payload_dict.get("amenities", {})
            system_ids = amenities_data.get("system_amenity_ids", [])
            custom_amenities = amenities_data.get("custom_amenities", [])

            # ── Rule 1: Validate system amenity IDs exist in DB ─────────────
            # validate_amenities returns the set of system amenity names (lowercase)
            system_names = await self.property_repo.validate_amenities(
                system_ids, custom_amenities
            )

            # ── Rule 2: Duplicate custom amenity names within the request ───
            custom_names_lower = [c["name"].lower() for c in custom_amenities]
            seen: set[str] = set()
            duplicates: list[str] = []
            for name in custom_names_lower:
                if name in seen:
                    duplicates.append(name)
                seen.add(name)

            if duplicates:
                dup_str = ", ".join(sorted(set(duplicates)))
                raise ResourceConflictException(
                    f"Duplicate custom amenity names are not allowed: {dup_str}"
                )

            # ── Rule 3: Custom amenity name must not match a system amenity ─
            conflicts = [
                c["name"] for c in custom_amenities if c["name"].lower() in system_names
            ]
            if conflicts:
                conflict_str = ", ".join(conflicts)
                raise ResourceConflictException(
                    f"These custom amenity names already exist as system amenities: {conflict_str}"
                )

            # ── Rule 4: Custom amenity name must not already exist on the property ─
            existing_property = await self.property_repo.get_property_by_id(
                property_id, tenant_id
            )
            if not existing_property:
                raise PropertyNotFoundException("Property not found or access denied")

            existing_custom = existing_property.custom_amenities or []
            existing_custom_names = {item["name"].lower() for item in existing_custom}

            already_exists = [
                c["name"]
                for c in custom_amenities
                if c["name"].lower() in existing_custom_names
            ]
            if already_exists:
                conflict_str = ", ".join(already_exists)
                raise ResourceConflictException(
                    f"These custom amenities already exist for this property: {conflict_str}"
                )

            # ── All checks passed — promote temp images → permanent paths ──────
            photos_data = payload_dict.get("photos", {})
            cover_url: str | None = photos_data.get("cover")
            gallery_urls: list[str] = photos_data.get("gallery", [])

            # Collect all non-None URLs for batch promotion
            all_urls_to_promote = []
            if cover_url:
                all_urls_to_promote.append(cover_url)
            all_urls_to_promote.extend(gallery_urls)

            if all_urls_to_promote:
                promoted_urls = await self.image_service.promote_temp_images(
                    urls=all_urls_to_promote,
                    property_id=str(property_id),
                    tenant_id=str(tenant_id),
                )
                # Reassemble the photos dict with promoted URLs (preserving order)
                promoted_iter = iter(promoted_urls)
                if cover_url:
                    payload_dict["photos"]["cover"] = next(promoted_iter)
                payload_dict["photos"]["gallery"] = [next(promoted_iter) for _ in gallery_urls]

            # ── Persist to DB with permanent URLs ────────────────────────────
            property_obj = await self.property_repo.create_photos_and_amenities(
                property_id, tenant_id, payload_dict
            )
            return PropertyPhotosAndAmenitiesResponse.model_validate(property_obj)

        except (
            PropertyNotFoundException,
            RepositoryException,
            AmenityNotFoundException,
            ResourceConflictException,
            ImageStorageException,
        ):
            raise
        except Exception as e:
            logger.error(
                f"[PropertyService] Error updating photos and amenities: {str(e)}"
            )
            raise ServiceException(
                internal_detail=f"Failed to update photos and amenities for property: {str(e)}"
            )

    async def create_localization(
        self,
        property_id: uuid.UUID,
        payload: Propertylocalization,
        tenant_id: uuid.UUID,
    ) -> PropertylocalizationResponse:
        logger.info(
            f"[PropertyService] creating localization for property {property_id}"
        )
        payload_dict = payload.model_dump()
        try:
            property_obj = await self.property_repo.create_localization(
                property_id, tenant_id, payload_dict
            )
            return PropertylocalizationResponse.model_validate(property_obj)
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error updating localization: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to update localization for property: {str(e)}"
            )

    async def create_brand_visual(
        self, property_id: uuid.UUID, payload: BrandVisual, tenant_id: uuid.UUID
    ) -> BrandVisualResponse:
        logger.info(
            f"[PropertyService] creating brand visual for property {property_id}"
        )
        payload_dict = payload.model_dump()
        try:
            property_obj = await self.property_repo.create_brand_visual(
                property_id, tenant_id, payload_dict
            )
            return BrandVisualResponse.model_validate(property_obj)
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error updating brand visual: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to update brand visual for property: {str(e)}"
            )

    async def get_tenant_properties_list(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> TenantPropertiesListResponse:
        """
        Retrieves properties and structures them into the TenantPropertiesListResponse Pydantic schema.
        """
        logger.info(f"[PropertyService] getting properties for tenant: {tenant_id}")
        try:
            properties, total_count = await self.property_repo.get_properties_by_tenant(
                tenant_id=tenant_id, skip=skip, limit=limit
            )
            formatted_properties = []

            # Iterate through each property independently
            for prop in properties:
                db_amenities = await self.property_repo.resolve_amenities_for_property(
                    prop.system_amenity_ids or []
                )

                property_system_amenities = [
                    SystemAmenityResponse.model_validate(amenity)
                    for amenity in db_amenities
                ]

                # CHANGE THIS DICTIONARY BLOCK:
                prop_data = {
                    **{c.name: getattr(prop, c.name) for c in prop.__table__.columns},
                    # FIX: Change 'system_amenity_ids' to 'system_amenities'
                    "system_amenities": property_system_amenities,
                    "custom_amenities": prop.custom_amenities or [],
                    "photos": prop.photos or {"cover": None, "gallery": []},
                }

                formatted_properties.append(PropertyResponse.model_validate(prop_data))

            return TenantPropertiesListResponse(
                tenant_id=tenant_id,
                total_count=total_count,
                properties=formatted_properties,
            )
        except RepositoryException:
            raise

        except Exception as e:
            logger.error(
                f"[PropertyService] Error getting properties for tenant: {str(e)}"
            )
            raise ServiceException(
                internal_detail=f"Failed to get properties for tenant: {str(e)}"
            )

        # Utilizing Pydantic v2's model_validate to handle SQLAlchemy structures natively
        return TenantPropertiesListResponse(
            tenant_id=tenant_id,
            total_count=total_count,
            properties=[PropertyResponse.model_validate(p) for p in properties],
        )

    async def get_all_system_amenities(self):
        logger.info("[PropertyService] getting all system amenities")
        try:
            amenities = await self.property_repo.get_all_system_amenities()
            return SystemAmenitiesListResponse(
                total_count=len(amenities),
                amenities=[SystemAmenityResponse.model_validate(a) for a in amenities],
            )
        except Exception as e:
            logger.error(
                f"[PropertyService] Error getting all system amenities: {str(e)}"
            )
            raise ServiceException(
                internal_detail=f"Failed to get all system amenities: {str(e)}"
            )

    async def delete_property(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ):
        logger.info(f"[PropertyService] deleting property {property_id}")
        try:
            await self.property_repo.delete_property(property_id, tenant_id)
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error deleting property: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to delete property: {str(e)}"
            )
