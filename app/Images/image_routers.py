import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status

from app.Images.image_services import ImageService
from app.middlewares.auth_middlewares import CurrentUser
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit
from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.pms.dependencies import get_image_service
from app.utils.logging import LoggerFactory
from app.utils.schemas import StandardResponse

logger = LoggerFactory.get_logger(__name__)

router = APIRouter(
    prefix="/properties",
    tags=["Image"],
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="image_upload")),
    ],
)


@router.post(
    "/images",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[List[str]],
)
async def upload_images(
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
            )
    fake_property_id = str(uuid.uuid4())

    uploaded_image_urls = await image_service.upload_property_images(
        folder_name=f"temp/{user.tenant_id}/properties/{fake_property_id}", files=files
    )

    return {"success": True, "data": uploaded_image_urls}


@router.post(
    "/{property_id}/rooms/images",
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
            )
    fake_room_id = str(uuid.uuid4())

    uploaded_image_urls = await image_service.upload_property_images(
        folder_name=f"temp/properties/{property_id}/rooms/{fake_room_id}", files=files
    )

    return {"success": True, "data": uploaded_image_urls}


@router.post("/image")
async def upload_image_property(
    user: CurrentUser,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File '{image.filename}' is invalid. Only valid image media files are accepted.",
        )

    fake_property_id = str(uuid.uuid4())
    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"temp/{user.tenant_id}/properties/{fake_property_id}", file=image
    )

    return {"success": True, "data": uploaded_image_url}


@router.post("/{property_id}/staffs/image")
async def upload_image_staff(
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File '{image.filename}' is invalid. Only valid image media files are accepted.",
        )

    fake_staff_id = str(uuid.uuid4())
    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"temp/{user.tenant_id}/properties/{property_id}/staffs/{fake_staff_id}",
        file=image,
    )

    return {"success": True, "data": uploaded_image_url}


@router.post("/{property_id}/rooms/image")
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File '{image.filename}' is invalid. Only valid image media files are accepted.",
        )

    fake_room_id = str(uuid.uuid4())

    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"temp/properties/{property_id}/rooms/{fake_room_id}", file=image
    )

    return {"success": True, "data": uploaded_image_url}


@router.post(
    "{property_id}/rooms/{room_id}/maintenance/images",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[List[str]],
)
async def upload_maintenance_images(
    staff: CurrentHousekeepingStaff,
    property_id: uuid.UUID = Path(...),
    room_id: uuid.UUID = Path(...),
    files: List[UploadFile] = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    logger.info("[ImageRouter] Uploading images")

    if staff.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )

    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk upload constraint violation: Maximum allowed limit is 5 files per request.",
        )

    for file in files:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
            )

    uploaded_image_urls = await image_service.upload_property_images(
        folder_name=f"properties/{property_id}/rooms/{room_id}/maintenance", files=files
    )

    return {"success": True, "data": uploaded_image_urls}



@router.post(
    "{property_id}/rooms/{room_id}/cleaning_status/images",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse[List[str]],
)
async def upload_cleaning_status_images(
    staff: CurrentHousekeepingStaff,
    property_id: uuid.UUID = Path(...),
    room_id: uuid.UUID = Path(...),
    file: UploadFile = File(...),
    image_service: ImageService = Depends(get_image_service),
):
    logger.info("[ImageRouter] Uploading images")

    if staff.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to upload images. You must belong to an active tenant.",
        )
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"File '{file.filename}' is invalid. Only valid image media files are accepted.",
        )

    uploaded_image_url = await image_service._process_and_upload_single(
        folder_name=f"properties/{property_id}/rooms/{room_id}/cleaning_status", file=file
    )

    return {"success": True, "data": uploaded_image_url}
