import asyncio
from fastapi import UploadFile
from app.utils.imgae_utils import process_image
from app.modules.pms.storage.image_storage import StorageFactory
from app.utils.exceptions import (
    ServiceException,
    ImageStorageException,
    InvalidImageException,
)
from app.utils.logging import LoggerFactory
import re

logger = LoggerFactory.get_logger(__name__)


class ImageService:
    def __init__(self):
        self.provider = StorageFactory.get_storage()

    async def upload_property_images(
        self, folder_name: str, files: list[UploadFile]
    ) -> list[str]:

        try:
            tasks = [
                self._process_and_upload_single(folder_name=folder_name, file=file)
                for file in files
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            uploaded_urls = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error uploading image: {str(result)}")
                    raise ServiceException(
                        f"Failed to process one or more images: {str(result)}"
                    )
                else:
                    uploaded_urls.append(result)
            return uploaded_urls
        except (InvalidImageException, ImageStorageException, ValueError):
            raise
        except Exception as e:
            logger.error(f"Error processing or uploading images: {str(e)}")
            raise ServiceException(f"Error processing or uploading images: {str(e)}")

    async def _process_and_upload_single(
        self, folder_name: str, file: UploadFile
    ) -> str:
        try:
            raw_bytes = await file.read()

            optimized_webp_bytes = await asyncio.to_thread(process_image, raw_bytes)

            saved_url = await self.provider.save_image(
                folder_name=folder_name, image_bytes=optimized_webp_bytes
            )

            logger.info(f"[ImageService] Image uploaded successfully to: {saved_url}")
            return saved_url
        except (InvalidImageException, ImageStorageException, ValueError):
            raise
        except Exception as e:
            logger.error(f"Error processing or uploading image: {str(e)}")
            raise ServiceException(f"Error processing or uploading image: {str(e)}")
        finally:
            await file.close()

    async def promote_temp_images(
        self,
        urls: list[str],
        property_id: str,
        tenant_id: str,
    ) -> list[str]:
        """
        Promotes a list of image URLs from temp/ to their permanent Cloudinary paths.

        For each URL:
          - If it does NOT contain '/temp/', it is already permanent → return as-is.
          - If it contains '/temp/', rename it in Cloudinary by stripping 'temp/' from
            the public_id, and replacing the fake_property_id folder with the real property_id.

        Temp public_id format:
            temp/{tenant_id}/properties/{property_id}/{filename}
        Permanent public_id format:
            {tenant_id}/properties/{property_id}/{filename}

        Returns the list of permanent URLs in the same order as input.
        Skips None/empty values transparently.
        """
        # ── Deduplicate before hitting Cloudinary ──────────────────────────
        # The same URL may appear as both cover and in gallery. Promoting the
        # same temp file twice concurrently causes "Resource not found" on the
        # second attempt because the file has already been moved by the first.
        unique_urls = list(dict.fromkeys(url for url in urls if url))  # preserve order, skip None

        async def _promote_one(url: str) -> str:
            if "/temp/" not in url:
                # Already a permanent URL — pass through unchanged
                return url

            old_public_id = self.extract_public_id_from_url(url)
            new_public_id = old_public_id.replace("temp/", "", 1)

            logger.info(
                f"[ImageService] Promoting image: {old_public_id} -> {new_public_id}"
            )
            result = await self.provider.rename_image(old_public_id, new_public_id)
            return result["url"]

        tasks = [_promote_one(url) for url in unique_urls]
        promoted_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build a mapping from original temp URL → promoted permanent URL
        url_map: dict[str, str] = {}
        for original, result in zip(unique_urls, promoted_results):
            if isinstance(result, Exception):
                logger.error(
                    f"[ImageService] Failed to promote image {original}: {result}"
                )
                raise ImageStorageException(
                    "Failed to promote one or more images from temp storage.",
                    internal_detail=str(result),
                )
            url_map[original] = result

        # Reconstruct the output list in the original order
        return [url_map[url] if url else url for url in urls]

    async def promote_room_temp_images(
        self,
        urls: list[str],
        property_id: str,
        real_room_id: str,
    ) -> list[str]:
        """
        Promotes room images from temp/ to their permanent paths.
        
        Temp path format:
            temp/properties/{property_id}/rooms/{fake_room_id}/{filename}
        Permanent path format:
            properties/{property_id}/rooms/{real_room_id}/{filename}
        """
        unique_urls = list(dict.fromkeys(url for url in urls if url))

        async def _promote_one(url: str) -> str:
            if "/temp/" not in url:
                return url

            old_public_id = self.extract_public_id_from_url(url)
            fake_room_id = self.extract_fake_id_from_public_id(old_public_id, "rooms")

            # Replace temp/ and swap the fake_room_id with real_room_id
            new_public_id = old_public_id.replace("temp/", "", 1)
            new_public_id = new_public_id.replace(fake_room_id, real_room_id, 1)

            logger.info(
                f"[ImageService] Promoting room image: {old_public_id} -> {new_public_id}"
            )
            result = await self.provider.rename_image(old_public_id, new_public_id)
            return result["url"]

        tasks = [_promote_one(url) for url in unique_urls]
        promoted_results = await asyncio.gather(*tasks, return_exceptions=True)

        url_map: dict[str, str] = {}
        for original, result in zip(unique_urls, promoted_results):
            if isinstance(result, Exception):
                logger.error(
                    f"[ImageService] Failed to promote room image {original}: {result}"
                )
                raise ImageStorageException(
                    "Failed to promote one or more room images from temp storage.",
                    internal_detail=str(result),
                )
            url_map[original] = result

        return [url_map[url] if url else url for url in urls]

    def extract_fake_id_from_public_id(self, public_id: str, segment: str) -> str:
        """
        public_id looks like:
            "temp/properties/9f3a1c2e-8b21-4a11-9c3d-1719999999/wtjpjac0dcyqv3epr5l6"

        We want the folder segment right after "{segment}":
            "9f3a1c2e-8b21-4a11-9c3d-1719999999"
        """
        parts = public_id.split("/")

        try:
            idx = parts.index(segment)
        except ValueError:
            raise ValueError(f"'{segment}' segment not found in public_id: {public_id}")

        if idx + 1 >= len(parts):
            raise ValueError(
                f"No folder segment after '{segment}' in public_id: {public_id}"
            )

        return parts[idx + 1]

    def extract_public_id_from_url(self, url: str) -> str:
        # https://res.cloudinary.com/<cloud>/image/upload/v1782893339/test/properties/.../file.webp
        try:
            after_upload = url.split("/upload/", 1)[1]
            # after_upload = "v1782893339/test/properties/.../wtjpjac0dcyqv3epr5l6.webp"

            # strip the leading version segment (v followed by digits)
            segments = after_upload.split("/", 1)
            if segments[0].startswith("v") and segments[0][1:].isdigit():
                after_upload = segments[1]

            # strip the file extension
            return re.sub(r"\.[^/.]+$", "", after_upload)
        except Exception as e:
            raise InvalidImageException(
                internal_detail=f"Invalid URL format: {url} , error occured {str(e)}"
            )

    def extract_fake_property_id_from_url(self, url: str) -> str:
        return self.extract_fake_property_id_from_public_id(
            self.extract_public_id_from_url(url)
        )
