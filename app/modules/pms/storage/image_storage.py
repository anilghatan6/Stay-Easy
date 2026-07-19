import uuid
import aiofiles
import asyncio
import cloudinary.uploader
import cloudinary.api
from abc import ABC, abstractmethod
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta
from app.utils.logging import LoggerFactory
from app.utils.exceptions import ImageStorageException

load_dotenv()

logger = LoggerFactory.get_logger(__name__)

class ImageStorageStrategy(ABC):
    @abstractmethod
    async def save_image(self, folder_name: str, image_bytes: bytes) -> str:
        pass

    @abstractmethod
    async def rename_image(self, old_public_id: str, new_public_id: str) -> dict:
        """Rename/move an image to a new path. Returns dict with 'url' and 'public_id'."""
        pass


class LocalImageStorage(ImageStorageStrategy):
    def __init__(self, base_path: str = "static/uploads"):
        self.base_path = Path(base_path)

    async def save_image(self, folder_name: str, image_bytes: bytes) -> str:
        logger.info(f"[LocalImageStorage] Saving image in {folder_name} folder")
        filename = f"{uuid.uuid4().hex}.webp"
        target_dir = self.base_path / folder_name
        
        # Ensure the specific folder (e.g., 'properties' or 'users') exists
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / filename

        # Asynchronously write the bytes to disk
        try:
            async with aiofiles.open(filepath, 'wb') as out_file:
                await out_file.write(image_bytes)
            logger.info(f"[LocalImageStorage] Image saved successfully at {filepath}")
            return f"/{self.base_path.name}/{folder_name}/{filename}"
        except Exception as e:
            logger.error(f"Error saving image to disk: {str(e)}")
            raise ImageStorageException("Error saving image to disk", f"Error saving image to disk: {str(e)}")

    async def rename_image(self, old_public_id: str, new_public_id: str) -> dict:
        """Local storage rename is a no-op placeholder — not needed for local dev."""
        logger.warning(
            f"[LocalImageStorage] rename_image called but not supported locally: {old_public_id} -> {new_public_id}"
        )
        return {"url": old_public_id, "public_id": new_public_id}


class CloudinaryImageStorage(ImageStorageStrategy):
    def __init__(self):
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
    
    async def save_image(self, folder_name: str, image_bytes: bytes) -> str:
        logger.info(f"[CloudinaryImageStorage] Uploading image to Cloudinary in {folder_name} folder")
        try:
            def _upload_to_cloudinary():
                return cloudinary.uploader.upload(
                    image_bytes,
                    folder=folder_name,
                    resource_type="image",
                    format="webp"
                )

            response = await asyncio.to_thread(_upload_to_cloudinary)
            
            secure_url = response.get("secure_url")
            if not secure_url:
                raise ValueError("Cloudinary response did not contain a valid secure_url parameter field.")
                
            logger.info(f"[CloudinaryImageStorage] Image uploaded successfully to Cloudinary at {secure_url}")
            return secure_url
        except Exception as e:
            logger.error(f"Error uploading image to Cloudinary: {str(e)}")
            raise ImageStorageException("Error uploading image to Cloudinary", f"Error uploading image to Cloudinary: {str(e)}")

    async def rename_image(self, old_public_id: str, new_public_id: str) -> dict:
        try:
            def _rename():
                return cloudinary.uploader.rename(
                    old_public_id,
                    new_public_id,
                    resource_type="image",
                    overwrite=True,   # if destination already exists, replace it
                    invalidate=True,  # purge CDN cache of the old URL
                )

            response = await asyncio.to_thread(_rename)

            return {
                "url": response.get("secure_url"),
                "public_id": response.get("public_id"),
            }
        except Exception as e:
            error_msg = str(e)

            # ── Idempotent promotion ──────────────────────────────────────────
            # "Resource not found" means the source (temp/) no longer exists.
            # This happens when the image was already promoted in a previous
            # (partially successful) request. In that case, check whether the
            # permanent destination already exists and return it directly.
            if "Resource not found" in error_msg or "resource not found" in error_msg.lower():
                logger.warning(
                    f"[CloudinaryImageStorage] Source not found during rename "
                    f"({old_public_id}). Checking if destination already exists..."
                )
                try:
                    def _check_destination():
                        return cloudinary.api.resource(new_public_id, resource_type="image")

                    resource_info = await asyncio.to_thread(_check_destination)
                    if resource_info and resource_info.get("secure_url"):
                        logger.info(
                            f"[CloudinaryImageStorage] Image already at permanent path: {new_public_id}"
                        )
                        return {
                            "url": resource_info["secure_url"],
                            "public_id": resource_info["public_id"],
                        }
                except Exception:
                    # Destination also doesn't exist — fall through to original error
                    pass

            logger.error(f"Error renaming image {old_public_id} -> {new_public_id}: {error_msg}")
            raise ImageStorageException("Error renaming image", error_msg)
    
    async def delete_temp_assets(self,public_id:str)->dict:
        try:
            def _delete():
                return cloudinary.uploader.destroy(
                    public_id,
                    resource_type="image",
                    invalidate=True,
                )
            
            response = await asyncio.to_thread(_delete)
            logger.info(f"[CloudinaryImageStorage] Image deleted successfully from Cloudinary at {public_id}")
            return response
        except Exception as e:
            logger.error(f"Error deleting image {public_id}: {str(e)}")
            raise ImageStorageException("Error deleting image", str(e))

    async def clean_old_temp_images(self):
        """
        Finds all images older than 24 hours under the "temp*" path and deletes them concurrently.
        """
        # 1. Calculate 24-hour cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        expression_time = cutoff_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        search_expression = f"uploaded_at:[* TO \"{expression_time}\"] AND public_id:temp*"
        logger.info(f"Scanning Cloudinary for stale temp assets: {search_expression}")

        try:
            # 2. Run the search query off the main thread (Cloudinary Search API is blocking)
            def _search():
                return cloudinary.Search()\
                    .expression(search_expression)\
                    .max_results(100)\
                    .execute()

            search_result = await asyncio.to_thread(_search)
            resources = search_result.get("resources", [])

            if not resources:
                logger.info("No temporary images older than 24 hours found.")
                return

            # 3. Extract public IDs
            public_ids = [asset["public_id"] for asset in resources]
            logger.info(f"Found {len(public_ids)} stale images. Executing concurrent deletion...")

            # 4. Fire all deletion tasks concurrently using asyncio.gather
            tasks = [self.delete_temp_assets(pid) for pid in public_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 5. Optional evaluation of concurrent execution results
            for pid, res in zip(public_ids, results):
                if isinstance(res, Exception):
                    logger.error(f"Failed concurrent deletion for {pid}: {res}")
                else:
                    logger.info(f"Concurrent deletion verified for {pid}")

        except Exception as e:
            logger.error(f"Failed to complete scheduled temp file sweep: {str(e)}")


class StorageFactory:
    @staticmethod
    def get_storage() -> ImageStorageStrategy:
        """
        Returns the appropriate storage strategy based on the provider string.
        """
        provider = os.getenv("IMAGE_STORAGE_PROVIDER")
        provider_clean = provider.strip().lower()
        
        if provider_clean == "local":
            logger.info("[StorageFactory] Using Local Storage")
            return LocalImageStorage()
        elif provider_clean == "cloudinary":
            logger.info("[StorageFactory] Using Cloudinary Storage")
            return CloudinaryImageStorage()
        else:
            raise ValueError(f"Unsupported storage provider: {provider}")