from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Path
from typing import List
from app.modules.auth.auth_middlewares import CurrentUser
from app.modules.pms.services.image_services import ImageService
from app.modules.pms.dependencies import get_image_service
from app.utils.schemas import StandardResponse
from app.utils.logging import LoggerFactory
import uuid

logger = LoggerFactory.get_logger(__name__)

router = APIRouter(prefix="/pms", tags=["Image"])


@router.post(
    "/properties/{property_id}/images",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[List[str]],
)
async def upload_images(
    property_id: uuid.UUID,
    user: CurrentUser,
    files: List[UploadFile] = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    logger.info("[ImageRouter] Uploading images")

    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )

    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk upload constraint violation: Maximum allowed limit is 5 files per request.",
        )

    # Enforce explicit image mime-type checking before starting file read routines
    for file in files:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
            )

    uploaded_image_urls = await image_service.upload_property_images(
        folder_name=f"temp/{user.tenant_id}/properties/{property_id}", files=files
    )

    return {"success": True, "data": uploaded_image_urls}


@router.post(
    "/properties/{property_id}/rooms/images",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[List[str]],
)
async def upload_room_images(
    user: CurrentUser,
    property_id: uuid.UUID = Path(...),
    files: List[UploadFile] = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    logger.info("[ImageRouter] Uploading images")

    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )

    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk upload constraint violation: Maximum allowed limit is 5 files per request.",
        )

    # Enforce explicit image mime-type checking before starting file read routines
    for file in files:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
            )
    fake_room_id = str(uuid.uuid4())

    uploaded_image_urls = await image_service.upload_property_images(
        folder_name=f"temp/properties/{property_id}/rooms/{fake_room_id}", files=files
    )

    return {"success": True, "data": uploaded_image_urls}


@router.post("/property/{property_id}/image")
async def upload_image_property(
    user: CurrentUser,
    property_id: uuid.UUID = Path(...),
    image: UploadFile = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )

    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File '{image.filename}' is invalid. Only valid image media files are accepted.",
        )

    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"temp/{user.tenant_id}/properties/{property_id}", file=image
    )

    return {"success": True, "data": uploaded_image_url}


@router.post("/property/{property_id}/rooms/image")
async def upload_image_room(
    user: CurrentUser,
    property_id: uuid.UUID = Path(...),
    image: UploadFile = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )

    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File '{image.filename}' is invalid. Only valid image media files are accepted.",
        )

    fake_room_id = str(uuid.uuid4())

    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"temp/properties/{property_id}/rooms/{fake_room_id}", file=image
    )

    return {"success": True, "data": uploaded_image_url}
