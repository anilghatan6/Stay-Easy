import asyncio
from fastapi import UploadFile
from app.Images.imgae_utils import process_image
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
        entity_folder: str,
        real_entity_id: str,
    ) -> list[str]:
        """
        Promotes images from temp/ to their permanent paths for any entity type.

        Temp path format:
            temp/.../{entity_folder}/{fake_entity_id}/{filename}
        Permanent path format:
            .../{entity_folder}/{real_entity_id}/{filename}

        Works identically for properties, rooms, staff, or any future entity —
        the folder name and real ID are the only things that differ per call site.
        """
        unique_urls = list(dict.fromkeys(url for url in urls if url))

        async def _promote_one(url: str) -> str:
            if "/temp/" not in url:
                return url

            old_public_id = self.extract_public_id_from_url(url)
            fake_entity_id = self.extract_fake_id_from_public_id(old_public_id, entity_folder)

            new_public_id = old_public_id.replace("temp/", "", 1)
            new_public_id = new_public_id.replace(fake_entity_id, real_entity_id, 1)

            logger.info(
                f"[ImageService] Promoting {entity_folder} image: {old_public_id} -> {new_public_id}"
            )
            result = await self.provider.rename_image(old_public_id, new_public_id)
            return result["url"]

        tasks = [_promote_one(url) for url in unique_urls]
        promoted_results = await asyncio.gather(*tasks, return_exceptions=True)

        url_map: dict[str, str] = {}
        for original, result in zip(unique_urls, promoted_results):
            if isinstance(result, Exception):
                logger.error(
                    f"[ImageService] Failed to promote {entity_folder} image {original}: {result}"
                )
                raise ImageStorageException(
                    f"Failed to promote one or more {entity_folder} images from temp storage.",
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

    async def delete_images_by_urls(self, urls: list[str]) -> None:
        """
        Best-effort Cloudinary cleanup for a list of image URLs.

        Extracts each URL's public_id and calls the provider's bulk
        delete_images(). Failures are logged but never re-raised — the
        caller's DB transaction has already committed, so this is
        intentionally non-fatal.

        Skips None/empty/non-Cloudinary values silently.
        """
        public_ids: list[str] = []
        for url in urls:
            if not url or "/upload/" not in url:
                continue
            try:
                pid = self.extract_public_id_from_url(url)
                public_ids.append(pid)
            except Exception as e:
                logger.warning(
                    f"[ImageService] Could not extract public_id from URL '{url}': {e}"
                )

        if not public_ids:
            return

        try:
            await self.provider.delete_images(public_ids)
            logger.info(
                f"[ImageService] Successfully deleted {len(public_ids)} image(s) from Cloudinary"
            )
        except Exception as e:
            logger.error(
                f"[ImageService] Non-fatal: failed to delete images from Cloudinary: {e}"
            )
