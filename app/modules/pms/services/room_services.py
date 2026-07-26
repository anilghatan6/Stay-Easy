from app.modules.pms.schemas.room_schemas import RoomTypeCreate
import uuid
import asyncio

from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.schemas.room_schemas import (
    RoomBulkCreateRequest,
    RoomBulkCreateResponse,
    RoomResponse,
    RoomTypeResponse,
    BedTypeResponse,
    # RoomTypeCreate,
    BedTypeCreate,
    RoomUpdate
)
from app.utils.exceptions import (
    PropertyNotFoundException,
    RepositoryException,
    RoomTypeAlreadyExistsException,
    BedTypeAlreadyExistsException,
    RoomNameAlreadyExistsException,
    ServiceException,
    UnauthorizedException,
    RoomNotFoundException,
    # AmenityNotFoundException,
    InvalidImageException,
    ImageStorageException,
)

from app.modules.pms.services.image_services import ImageService
from app.utils.logging import LoggerFactory
from datetime import date
logger = LoggerFactory.get_logger(__name__)


class RoomService:
    def __init__(
        self,
        room_repo: RoomRepository,
        property_repo: PropertyRepository,
        image_service: ImageService,
    ):
        self.room_repo = room_repo
        self.property_repo = property_repo
        self.image_service = image_service

    async def _promote_room_images_if_any(
        self, rooms_data: list[dict], property_id: uuid.UUID
    ) -> None:
        try:
            tasks = []

            async def _promote_single_room(room: dict):
                real_room_id = uuid.uuid4()
                room["id"] = real_room_id

                photos_data = room.get("photos", {})
                if not photos_data:
                    return

                cover_url = photos_data.get("cover")
                gallery_urls = photos_data.get("gallery", [])

                urls_to_promote = []
                if cover_url:
                    urls_to_promote.append(cover_url)
                urls_to_promote.extend(gallery_urls)

                if urls_to_promote:
                    promoted_urls = await self.image_service.promote_room_temp_images(
                        urls=urls_to_promote,
                        property_id=str(property_id),
                        real_room_id=str(real_room_id),
                    )
                    promoted_iter = iter(promoted_urls)
                    if cover_url:
                        room["photos"]["cover"] = next(promoted_iter)
                    room["photos"]["gallery"] = [
                        next(promoted_iter) for _ in gallery_urls
                    ]

            for room in rooms_data:
                tasks.append(_promote_single_room(room))

            if tasks:
                await asyncio.gather(*tasks)
        except ImageStorageException:
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error promoting room images: {str(e)}")
            raise ServiceException(str(e))

    async def _validate_property(self, property_id: uuid.UUID, tenant_id: uuid.UUID):
        property_obj = await self.property_repo.get_property_by_id(
            property_id, tenant_id
        )
        if not property_obj:
            raise PropertyNotFoundException("Property not found")

        if property_obj.tenant_id != tenant_id:
            raise UnauthorizedException("You do not own this property")

        return property_obj

    async def _validate_room_bed_and_type(
        self, property_id: uuid.UUID, room_types: list[str], bed_types: list[str]
    ):

        for room_type in room_types:
            room_type_obj = await self.room_repo.get_existing_room_type_name(
                property_id, room_type
            )
            if room_type_obj:
                raise RoomTypeAlreadyExistsException("Room type name already exists")

        for bed_type in bed_types:
            bed_type_obj = await self.room_repo.get_exisiting_bed_type_name(
                property_id, bed_type
            )
            if bed_type_obj:
                raise BedTypeAlreadyExistsException("Bed type name already exists")

    async def create_rooms(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
        payload: RoomBulkCreateRequest,
    ) -> RoomBulkCreateResponse:
        logger.info(f"[RoomService] Creating rooms for property {property_id}")
        try:
            property_obj = await self._validate_property(property_id, tenant_id)
            payload_dict = payload.model_dump()
            rooms_data = payload_dict["rooms"]
            logger.info(f"[RoomService] Rooms data: {rooms_data}")

            room_names = [room["room_name"] for room in rooms_data]
            existing_room_names = await self.room_repo.get_existing_room_names(
                property_id, room_names
            )
            if existing_room_names:
                raise RoomNameAlreadyExistsException(
                    f"Room name(s) already exists: {[room.room_name for room in existing_room_names]}"
                )

            # Promote temporary room images to their permanent paths
            await self._promote_room_images_if_any(rooms_data, property_obj.id)

            created_rooms = await self.room_repo.create_rooms(
                property_obj.id, rooms_data
            )
            return RoomBulkCreateResponse(
                rooms=[RoomResponse.model_validate(r) for r in created_rooms]
            )
        except (
            PropertyNotFoundException,
            UnauthorizedException,
            RoomNameAlreadyExistsException,
            RepositoryException,
            InvalidImageException,
            ImageStorageException,
        ):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing room creation batch: {str(e)}")
            raise ServiceException(str(e))

    async def create_room_type(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, payload: RoomTypeCreate
    ) -> RoomTypeResponse:
        logger.info(f"[RoomService] creating room type for property {property_id}")
        try:
            property_obj = await self._validate_property(property_id, tenant_id)
            room_type_dict = payload.model_dump()
            existing_room_type_name = await self.room_repo.get_existing_room_type_name(
                property_id, room_type_dict["room_type_name"]
            )
            if existing_room_type_name:
                logger.info(
                    f"[RoomService] Room type name already exists: {room_type_dict['room_type_name']}"
                )
                raise RoomTypeAlreadyExistsException("Room type name already exists")
            created_room_type = await self.room_repo.create_room_type(
                property_obj.id, room_type_dict
            )
            return RoomTypeResponse.model_validate(created_room_type)

        except (RoomTypeAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing room type creation: {str(e)}")
            raise ServiceException(str(e))

    async def create_bed_type(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, payload: BedTypeCreate
    ) -> BedTypeResponse:
        logger.info(f"[RoomService] creating bed type for property {property_id}")
        try:
            property_obj = await self._validate_property(property_id, tenant_id)
            bed_type_dict = payload.model_dump()
            existing_bed_type_name = await self.room_repo.get_existing_bed_type_name(
                property_id, bed_type_dict["bed_name"]
            )
            if existing_bed_type_name:
                logger.info(
                    f"[RoomService] Bed type name already exists: {bed_type_dict['bed_name']}"
                )
                raise BedTypeAlreadyExistsException("Bed type name already exists")
            created_bed_type = await self.room_repo.create_bed_type(
                property_obj.id, bed_type_dict
            )
            return BedTypeResponse.model_validate(created_bed_type)

        except (BedTypeAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing bed type creation: {str(e)}")
            raise ServiceException(str(e))

    async def get_all_rooms(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[RoomResponse]:
        logger.info(f"[RoomService] Getting all rooms for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            rooms = await self.room_repo.get_all_rooms(property_id)
            logger.info(
                f"[RoomService] Found {len(rooms)} rooms for property {property_id}"
            )
            return [RoomResponse.model_validate(room) for room in rooms]

        except (PropertyNotFoundException, UnauthorizedException, RepositoryException):
            raise

        except Exception as e:
            logger.error(f"[RoomService] Error executing get all rooms: {str(e)}")
            raise ServiceException(str(e))

    async def get_all_room_types(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[RoomTypeResponse]:
        logger.info(f"[RoomService] getting room types for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            room_types = await self.room_repo.get_all_room_types(property_id)
            logger.info(
                f"[RoomService] Found {len(room_types)} room types for property {property_id}"
            )
            return [
                RoomTypeResponse.model_validate(room_type) for room_type in room_types
            ]

        except (PropertyNotFoundException, UnauthorizedException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing get all room types: {str(e)}")
            raise ServiceException(str(e))

    async def get_all_bed_types(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[BedTypeResponse]:
        logger.info(f"[RoomService] getting bed types for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            bed_types = await self.room_repo.get_all_bed_types(property_id)
            logger.info(
                f"[RoomService] Found {len(bed_types)} bed types for property {property_id}"
            )
            return [BedTypeResponse.model_validate(bed_type) for bed_type in bed_types]
        except (PropertyNotFoundException, UnauthorizedException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing get all bed types: {str(e)}")
            raise ServiceException(str(e))

    async def delete_room(
        self,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
    ) -> dict[str]:
        logger.info(f"[RoomService] Deleting room {room_id} for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            await self.room_repo.delete_room(room_id)
            logger.info(f"[RoomService] Room {room_id} deleted successfully")
            return {"message": "Room deleted successfully"}
        except (PropertyNotFoundException, UnauthorizedException, RepositoryException, RoomNotFoundException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing delete room: {str(e)}")
            raise ServiceException(str(e))


    async def get_room(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> RoomResponse:
        logger.info(f"[RoomService] Getting room {room_id} for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            room = await self.room_repo.get_room(room_id)
            if not room:
                logger.info(
                    f"[RoomService] Room {room_id} not found for property {property_id}"
                )
                raise RoomNotFoundException(
                    internal_detail=f"Room {room_id} not found for property {property_id}"
                )
            logger.info(f"[RoomService] Room {room_id} found successfully")
            return RoomResponse.model_validate(room)
        except (
            PropertyNotFoundException,
            UnauthorizedException,
            RepositoryException,
            RoomNotFoundException,
        ):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing get room: {str(e)}")
            raise ServiceException(str(e))

    async def update_room(
        self,
        property_id:uuid.UUID,
        tenant_id:uuid.UUID,
        room_id:uuid.UUID,
        payload:RoomUpdate
    ):
                        
        logger.info(f"[RoomService] Updating room {room_id} for property {property_id}")
        try:
            await self._validate_property(property_id, tenant_id)
            payload_dict = payload.model_dump(exclude_unset=True)
            if payload_dict.get("room_name"):
                existing_room_name = await self.room_repo.get_room_by_name(
                    property_id=property_id,
                    room_name=payload_dict.get("room_name"),
                    exclude_room_id=room_id
                )
                if existing_room_name:
                    logger.info(
                        f"[RoomService] Room name {payload_dict.get('room_name')} already exists"
                    )
                    raise RoomNameAlreadyExistsException(
                        f"Room name '{payload_dict.get('room_name')}' already exists"
                    )
            room = await self.room_repo.update_room(room_id, payload_dict)
            logger.info(f"[RoomService] Room {room_id} updated successfully")
            return RoomResponse.model_validate(room)
        except (
            PropertyNotFoundException,
            UnauthorizedException,
            RepositoryException,
            RoomNotFoundException,
            RoomNameAlreadyExistsException,
        ):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing update room: {str(e)}")
            raise ServiceException(str(e))

    
    async def get_available_rooms(
        self,
        property_id: uuid.UUID,
        checkin_date: date,
        checkout_date: date,
    ) -> list[RoomResponse]:
        logger.info(f"[RoomService] Getting available rooms for property {property_id}")
        try:
            rooms = await self.room_repo.get_available_rooms_for_property(
                property_id, checkin_date, checkout_date
            )
            if not rooms:
                return []
            return [RoomResponse.model_validate(room) for room in rooms]
        except (PropertyNotFoundException, UnauthorizedException, RepositoryException, RoomNotFoundException):
            raise
        except Exception as e:
            logger.error(f"[RoomService] Error executing get available rooms: {str(e)}")
            raise ServiceException(str(e))