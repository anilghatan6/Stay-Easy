import uuid
import secrets
import string
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff_mgmt.repositories.staffs_repository import StaffRepository
from app.modules.pms.services.image_services import ImageService
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.services.auth_services import AuthService
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
    StaffAlreadlyExistException,
    StaffNotFound,
    PropertyNotFoundException,
    ImageStorageException,
)

from app.modules.staff_mgmt.schemas.staffs_schemas import (
    CreateStaffRequest,
    UpdateStaffRequest,
    StaffResponse,
)
from app.utils.mail_services import send_staff_welcome_email
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class StaffService:
    def __init__(
        self,
        db: AsyncSession,
        staff_repo: StaffRepository,
        prop_repo: PropertyRepository,
        image_service: ImageService,
        user_repo: UserRepository,
        security_service: AuthService,
    ):
        self.db = db
        self.staff_repo = staff_repo
        self.prop_repo = prop_repo
        self.image_service = image_service
        self.user_repo = user_repo
        self.security_service = security_service

    async def _promote_staff_images_if_any(
        self, photos_data: dict, staff_id: uuid.UUID
    ) -> dict:
        """
        Promotes any temp-uploaded staff photos (profile, citizenship_front,
        citizenship_back) into their permanent storage location, tied to the
        real staff_id. Returns the updated photos dict with promoted URLs.
        Fields left as None/absent are simply skipped.
        """
        try:
            if not photos_data:
                return photos_data

            photo_keys = ["profile", "citizenship_front", "citizenship_back"]

            urls_to_promote = []
            keys_with_urls = []

            for key in photo_keys:
                url = photos_data.get(key)
                if url:
                    urls_to_promote.append(url)
                    keys_with_urls.append(key)

            if not urls_to_promote:
                return photos_data

            promoted_urls = await self.image_service.promote_temp_images(
                urls=urls_to_promote,
                entity_folder="staffs",
                real_entity_id=str(staff_id),
            )

            for key, promoted_url in zip(keys_with_urls, promoted_urls):
                photos_data[key] = promoted_url

            return photos_data

        except ImageStorageException:
            raise
        except Exception as e:
            logger.error(f"[StaffService] Error promoting staff images: {str(e)}")
            raise ServiceException(str(e))

    def _generate_temp_password(self, length: int = 8) -> str:
        """Generates a secure temporary password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def create_staff(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID, payload: CreateStaffRequest
    ) -> StaffResponse:
        logger.info(f"[StaffService] Creating staff for tenant {tenant_id}")

        staff_data = payload.model_dump()
        staff_id = uuid.uuid4()
        try:
            existing = await self.staff_repo.get_by_email(staff_data["email"])
            if existing is not None:
                raise StaffAlreadlyExistException(
                    f"A staff member with email {staff_data['email']} already exists"
                )

            existing_user = await self.user_repo.get_user_by_email(staff_data["email"])
            if existing_user is not None:
                raise StaffAlreadlyExistException(
                    f"A user with email {staff_data['email']} already exists"
                )

            property_obj = await self.prop_repo.get_property_by_id(
                property_id, tenant_id
            )
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")

            staff_data["staff_id"] = staff_id

            # Pass only the photos sub-dict so _promote_staff_images_if_any
            # can correctly find keys like "profile", "citizenship_front", etc.
            photos = staff_data.get("photos") or {}
            promoted_photos = await self._promote_staff_images_if_any(photos, staff_id)
            staff_data["photos"] = promoted_photos

            temp_password = self._generate_temp_password(8)
            hashed_password = self.security_service.get_password_hash(temp_password)

            user_data = {
                "email": staff_data["email"],
                "phone": staff_data["phone_number"],
                "full_name": staff_data["full_name"],
                "role": staff_data["job_role"],
                "tenant_id": tenant_id,
                "hashed_password": hashed_password,
                "is_active": True,
            }

            await self.user_repo.register_user(user=user_data)

            staff = await self.staff_repo.create_staff(
                tenant_id=tenant_id, property_id=property_id, data=staff_data
            )

            await self.db.commit()
            await self.db.refresh(staff, attribute_names=["property_assignments"])
            logger.info(f"[StaffService] Staff created successfully: {staff.id}")
            try:
                await send_staff_welcome_email(
                    to_email=user_data["email"],
                    full_name=user_data["full_name"],
                    job_role=user_data["role"],
                    temp_password=temp_password,
                    property_name=property_obj.name,
                )
            except Exception as email_err:
                logger.error(
                    f"[StaffService] Failed to send welcome email to {user_data['email']}: {email_err}",
                    exc_info=True,
                )

            return StaffResponse.model_validate(staff)

        except (
            StaffAlreadlyExistException,
            PropertyNotFoundException,
            RepositoryException,
        ):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[StaffService] Error creating staff: {e}", exc_info=True)
            raise ServiceException("Error creating staff")

    async def get_staff_by_id(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffResponse:
        try:
            property_obj = await self.prop_repo.get_property_by_id(
                property_id, tenant_id
            )
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")

            staff = await self.staff_repo.get_by_id(staff_id)
            if staff is None:
                raise StaffNotFound("Staff member not found")

            logger.info(f"[StaffService] Staff retrieved successfully: {staff.id}")
            return StaffResponse.model_validate(staff)

        except (StaffNotFound, PropertyNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[StaffService] Error getting staff: {e}", exc_info=True)
            raise ServiceException("Error getting staff")

    async def list_staff(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 10
    ) -> list[StaffResponse]:
        try:
            staff_list, total = await self.staff_repo.list_by_tenant(
                tenant_id, skip, limit
            )
            logger.info("[StaffService] Staff list retribed successfully for tenant")
            return ([StaffResponse.model_validate(s) for s in staff_list], total)

        except RepositoryException:
            raise

        except Exception as e:
            logger.error(f"[StaffService] Error listing staff: {e}", exc_info=True)
            raise ServiceException("Error listing staff")

    async def list_staff_by_property(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
    ) -> list[StaffResponse]:
        try:
            property_obj = await self.prop_repo.get_property_by_id(
                property_id, tenant_id
            )
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")

            staff_list, total = await self.staff_repo.list_by_property(
                property_id, skip, limit
            )
            logger.info("[StaffService] Staff list retrieved successfully for property")
            return ([StaffResponse.model_validate(s) for s in staff_list], total)

        except (RepositoryException, PropertyNotFoundException):
            raise

        except Exception as e:
            logger.error(
                f"[StaffService] Error listing staff by property: {e}", exc_info=True
            )
            raise ServiceException("Error listing staff by property")

    async def update_staff(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        staff_id: uuid.UUID,
        payload: UpdateStaffRequest,
    ) -> StaffResponse:
        logger.info(f"[StaffService] Updating staff: {staff_id}")
        try:
            property_obj = await self.prop_repo.get_property_by_id(
                property_id, tenant_id
            )
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")

            staff = await self.staff_repo.get_by_id(staff_id)
            if staff is None:
                raise StaffNotFound("Staff member not found")

            if payload.email and payload.email != staff.email:
                email_owner = await self.staff_repo.get_by_email(payload.email)
                if email_owner is not None and email_owner.id != staff_id:
                    raise StaffAlreadlyExistException(
                        f"A staff member with email {payload.email} already exists"
                    )

            update_data = payload.model_dump(exclude_unset=True)

            # Handle photo promotion if photos are included in the update payload
            if "photos" in update_data and update_data["photos"]:
                incoming_photos = update_data["photos"]

                current_photos = staff.photos or {}
                merged_photos = {**current_photos, **incoming_photos}
                active_photos_to_promote = {
                    k: v for k, v in merged_photos.items() if v is not None
                }
                promoted_photos = await self._promote_staff_images_if_any(
                    active_photos_to_promote, staff_id
                )
                update_data["photos"] = promoted_photos

            if update_data:
                await self.staff_repo.update_staff_fields(staff_id, update_data)

            await self.db.commit()
            await self.db.refresh(staff)

            logger.info(f"[StaffService] Staff updated successfully: {staff_id}")
            return StaffResponse.model_validate(staff)

        except (
            PropertyNotFoundException,
            StaffNotFound,
            StaffAlreadlyExistException,
            RepositoryException,
        ):
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            logger.error("Error updating staff", exc_info=True)
            raise ServiceException("Error updating staff")

    async def delete_staff(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID, staff_id: uuid.UUID
    ) -> None:
        try:
            property_obj = await self.prop_repo.get_property_by_id(
                property_id, tenant_id
            )
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")

            # Collect photo URLs before deleting the DB row
            staff = await self.staff_repo.get_by_id(staff_id)
            if staff is None:
                raise StaffNotFound("Staff member not found")

            photos: dict = staff.photos or {}
            photo_urls = [
                photos.get("profile"),
                photos.get("citizenship_front"),
                photos.get("citizenship_back"),
            ]

            deleted = await self.staff_repo.delete_staff(staff_id)
            if not deleted:
                raise StaffNotFound("Staff member not found")

            await self.db.commit()
            logger.info(f"[StaffService] Staff deleted successfully: {staff_id}")

            # Best-effort Cloudinary cleanup (non-fatal)
            await self.image_service.delete_images_by_urls(photo_urls)

        except (StaffNotFound, PropertyNotFoundException, RepositoryException):
            await self.db.rollback()
            raise

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting staff: {e}", exc_info=True)
            raise ServiceException("Error deleting staff")
