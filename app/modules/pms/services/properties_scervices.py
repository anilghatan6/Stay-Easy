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
    PropertyBookingsResponse,
    UpdatePropertyInfo,
    SpecificPropertyResponse
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
from decimal import Decimal

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
                payload_dict["photos"]["gallery"] = [
                    next(promoted_iter) for _ in gallery_urls
                ]

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
    ) -> tuple[TenantPropertiesListResponse, int]:
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
                properties=formatted_properties,
            ), total_count
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
            # Fetch property with rooms eagerly to capture all photo URLs before deletion
            property_obj = await self.property_repo.get_property_with_rooms(
                property_id, tenant_id
            )
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")

            # Collect all photo URLs: property cover/gallery + every room's cover/gallery
            all_photo_urls: list[str] = []

            prop_photos: dict = property_obj.photos or {}
            if prop_photos.get("cover"):
                all_photo_urls.append(prop_photos["cover"])
            all_photo_urls.extend(prop_photos.get("gallery") or [])

            for room in (property_obj.rooms or []):
                room_photos: dict = room.photos or {}
                if room_photos.get("cover"):
                    all_photo_urls.append(room_photos["cover"])
                all_photo_urls.extend(room_photos.get("gallery") or [])

            await self.property_repo.delete_property(property_id, tenant_id)

            # Best-effort Cloudinary cleanup (non-fatal)
            await self.image_service.delete_images_by_urls(all_photo_urls)

        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error deleting property: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to delete property: {str(e)}"
            )

    async def get_property_by_id(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PropertyResponse:
        logger.info(f"[PropertyService] getting property {property_id}")
        try:
            property_obj = await self.property_repo.get_property_by_id(
                property_id, tenant_id
            )
            if not property_obj:
                raise PropertyNotFoundException("Property not found")

            # Fetching system amenities
            db_amenities = await self.property_repo.resolve_amenities_for_property(
                property_obj.system_amenity_ids or []
            )

            # Formatting system amenities for response
            property_system_amenities = [
                SystemAmenityResponse.model_validate(amenity)
                for amenity in db_amenities
            ]

            # Preparing the property data dictionary
            prop_data = {
                **{
                    c.name: getattr(property_obj, c.name)
                    for c in property_obj.__table__.columns
                },
                "system_amenities": property_system_amenities,
                "custom_amenities": property_obj.custom_amenities or [],
                "photos": property_obj.photos or {"cover": None, "gallery": []},
            }

            return PropertyResponse.model_validate(prop_data)

        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error getting property: {str(e)}")
            raise ServiceException(internal_detail=f"Failed to get property: {str(e)}")

    async def toggle_property_activation(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict:
        logger.info(f"[PropertyService] Toggling activation for property {property_id}")
        try:
            new_status = await self.property_repo.toggle_property_activation(
                property_id, tenant_id
            )
            if new_status:
                return {"success": True, "data": "property is activated "}
            else:
                return {"success": True, "data": "property is deactivated"}
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(
                f"[PropertyService] Error toggling property activation: {str(e)}"
            )
            raise ServiceException(
                internal_detail=f"Failed to toggle property activation: {str(e)}"
            )

    async def get_number_of_floors(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict[str, int]:
        logger.info("[PropertyService] Getting the number of floors")
        try:
            no_of_floors = await self.property_repo.get_number_of_floors(
                property_id, tenant_id
            )
            return {"number_of_floors": no_of_floors}
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error getting number of floors: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to get number of floors: {str(e)}"
            )

    async def get_specific_property(self, property_id: uuid.UUID) -> SpecificPropertyResponse:
        logger.info("[PropertyService] Getting the specific property")
        try:
            property = await self.property_repo.get_by_id(property_id)
            if not property:
                raise PropertyNotFoundException("Property not found")

            if not property.is_active:
                raise PropertyNotFoundException("Property Not Found ")

            owner_name = property.tenant.owner.full_name
            property_data = PropertyResponse.model_validate(property).model_dump()

            return SpecificPropertyResponse(
                owner_name=owner_name,
                **property_data
            )
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error getting specific property: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to get specific property: {str(e)}"
            )

    async def get_property_bookings(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, skip: int, limit: int
    ) -> tuple[list[PropertyBookingsResponse], int]:
        logger.info(
            f"[PropertyService] Getting the property bookings for property {property_id}"
        )
        try:
            property_obj = await self.property_repo.get_property_by_id(
                property_id, tenant_id
            )
            if not property_obj:
                raise PropertyNotFoundException("Property not found or access denied")
            bookings, total_count = await self.property_repo.get_property_bookings(
                property_id, tenant_id, skip, limit
            )

            formatted_bookings = []
            for booking in bookings:
                room_names = [
                    br.room_unit.room_name
                    for br in booking.booking_rooms
                    if br.room_unit and br.room_unit.room_name
                ]

                formatted_booking = {
                    "id": booking.id,
                    "guest_name": booking.guest.full_name,
                    "guest_email": booking.guest.email,
                    "booking_number": booking.ref_number,
                    "room_names": room_names,
                    "checkin_date": booking.checkin_date,
                    "checkout_date": booking.checkout_date,
                    "status": str(booking.status),
                    "payment_gateway": booking.payment_gateway,
                    "subtotal": Decimal(booking.subtotal)
                    if booking.subtotal
                    else Decimal(0),
                    "special_offer_discount": Decimal(booking.special_offer_discount)
                    if booking.special_offer_discount
                    else Decimal(0),
                    "coupon_code": booking.coupon_code if booking.coupon_code else None,
                    "coupon_discount": Decimal(booking.coupon_discount)
                    if booking.coupon_discount
                    else Decimal(0),
                    "total_amount": Decimal(booking.total_amount)
                    if booking.total_amount
                    else Decimal(0),
                    "created_at": booking.created_at,
                }
                formatted_bookings.append(formatted_booking)

            return [
                PropertyBookingsResponse(**booking) for booking in formatted_bookings
            ], total_count
        except (PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error getting property bookings: {str(e)}")
            raise ServiceException(
                internal_detail=f"Failed to get property bookings: {str(e)}"
            )

    async def update_property_by_id(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
        payload: UpdatePropertyInfo,
    ) -> PropertyResponse:
        logger.info(f"[PropertyService] Updating property {property_id} for tenant {tenant_id}")
        try:
            # 1. Fetch existing property
            existing_property = await self.property_repo.get_property_by_id(
                property_id, tenant_id
            )
            if not existing_property:
                raise PropertyNotFoundException("Property not found or access denied")

            update_data = payload.model_dump(exclude_unset=True)

            if not update_data:
                # Nothing to update, return current property state
                return await self.get_property_by_id(property_id, tenant_id)

            # 2. Name Uniqueness Check
            if "name" in update_data and update_data["name"] != existing_property.name:
                name_collision = await self.property_repo.get_property_by_name(
                    update_data["name"], tenant_id
                )
                if name_collision and name_collision.id != property_id:
                    raise PropertyAlreadyExistsException(
                        f"Property with name '{update_data['name']}' already exists"
                    )

            # 3. System & Custom Amenities Validation
            if "system_amenity_ids" in update_data or "custom_amenities" in update_data:
                new_system_ids = update_data.get(
                    "system_amenity_ids", existing_property.system_amenity_ids or []
                )
                raw_custom = update_data.get(
                    "custom_amenities", existing_property.custom_amenities or []
                )

                # Convert custom amenities items if pydantic models
                new_custom_amenities = [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in raw_custom
                ]

                # Validate system amenities exist
                system_names = await self.property_repo.validate_amenities(
                    new_system_ids, new_custom_amenities
                )

                # Check duplicate custom amenity names within payload if custom_amenities was provided
                if "custom_amenities" in update_data and new_custom_amenities:
                    custom_names_lower = [c["name"].lower() for c in new_custom_amenities]
                    seen = set()
                    duplicates = []
                    for c_name in custom_names_lower:
                        if c_name in seen:
                            duplicates.append(c_name)
                        seen.add(c_name)

                    if duplicates:
                        dup_str = ", ".join(sorted(set(duplicates)))
                        raise ResourceConflictException(
                            f"Duplicate custom amenity names are not allowed: {dup_str}"
                        )

                    # Custom amenity name must not match a system amenity
                    conflicts = [
                        c["name"] for c in new_custom_amenities if c["name"].lower() in system_names
                    ]
                    if conflicts:
                        conflict_str = ", ".join(conflicts)
                        raise ResourceConflictException(
                            f"These custom amenity names already exist as system amenities: {conflict_str}"
                        )

                if "custom_amenities" in update_data:
                    update_data["custom_amenities"] = new_custom_amenities

            # 4. Image Promotion (Photos & Brand Logo)
            urls_to_promote = []
            if "brand_logo_url" in update_data and update_data["brand_logo_url"]:
                urls_to_promote.append(update_data["brand_logo_url"])

            photos_payload = update_data.get("photos")
            if photos_payload:
                if isinstance(photos_payload, dict):
                    cover = photos_payload.get("cover")
                    gallery = photos_payload.get("gallery") or []
                else:
                    cover = photos_payload.cover
                    gallery = photos_payload.gallery or []

                if cover:
                    urls_to_promote.append(cover)
                if gallery:
                    urls_to_promote.extend(gallery)

            if urls_to_promote:
                promoted_urls = await self.image_service.promote_temp_images(
                    urls=urls_to_promote,
                    property_id=str(property_id),
                    tenant_id=str(tenant_id),
                )
                promoted_map = dict(zip(urls_to_promote, promoted_urls))

                if "brand_logo_url" in update_data and update_data["brand_logo_url"]:
                    update_data["brand_logo_url"] = promoted_map.get(
                        update_data["brand_logo_url"], update_data["brand_logo_url"]
                    )

                if photos_payload:
                    existing_photos = existing_property.photos or {"cover": None, "gallery": []}
                    updated_photos = {
                        "cover": existing_photos.get("cover"),
                        "gallery": list(existing_photos.get("gallery") or []),
                    }

                    if isinstance(photos_payload, dict):
                        cov = photos_payload.get("cover")
                        gal = photos_payload.get("gallery")
                    else:
                        cov = photos_payload.cover
                        gal = photos_payload.gallery

                    if cov is not None:
                        updated_photos["cover"] = promoted_map.get(cov, cov)

                    if gal is not None:
                        updated_photos["gallery"] = [
                            promoted_map.get(g_url, g_url) for g_url in gal
                        ]

                    update_data["photos"] = updated_photos

            # 5. Persist Update
            await self.property_repo.update_property(property_id, tenant_id, update_data)

            # 6. Fetch and return full PropertyResponse
            return await self.get_property_by_id(property_id, tenant_id)

        except (
            PropertyNotFoundException,
            PropertyAlreadyExistsException,
            AmenityNotFoundException,
            ResourceConflictException,
            ImageStorageException,
            RepositoryException,
        ):
            raise
        except Exception as e:
            logger.error(f"[PropertyService] Error updating property: {str(e)}", exc_info=True)
            raise ServiceException(
                internal_detail=f"Failed to update property: {str(e)}"
            )

