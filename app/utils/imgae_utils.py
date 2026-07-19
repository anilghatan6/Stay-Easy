
# import uuid
# from io import BytesIO
# from pathlib import Path
# from PIL import Image, ImageOps, UnidentifiedImageError
# from .exceptions import InvalidImageException

# # Crucial: Prevent large image decompression attacks
# Image.MAX_IMAGE_PIXELS = 25_000_000  # Max ~25 Megapixels (approx. 5000x5000)


# PROPERTY_PICS_DIR = Path("static/uploads/properties")
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB strict limit


# def process_property_image(content: bytes) -> str:
#     """
#     Synchronous, CPU-bound image processing function.
#     Resizes property photos for optimal Web/Mobile viewing without cropping.
#     """
#     # 1. Guard against memory exhaustion attacks
#     if len(content) > MAX_FILE_SIZE:
#         raise InvalidImageException(
#             "File size exceeds the maximum limit of 10MB.",
#             f"File size is {len(content)} bytes",
#         )

#     try:
#         # 2. Open image inside context manager safely
#         with Image.open(BytesIO(content)) as original:
#             # Auto-orient based on camera EXIF data
#             img = ImageOps.exif_transpose(original)

#             # Ensure image is in RGB mode
#             if img.mode in ("RGBA", "LA", "P"):
#                 img = img.convert("RGB")

#             # Preserve aspect ratio within bounding box
#             img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

#             # Generate unique paths safely
#             filename = f"{uuid.uuid4().hex}.webp"
#             filepath = PROPERTY_PICS_DIR / filename

#             # Ensure target directories are safely created
#             PROPERTY_PICS_DIR.mkdir(parents=True, exist_ok=True)

#             # 3. Save as optimized WebP with compression flags enabled
#             img.save(filepath, "WEBP", quality=80, optimize=True, lossless=False)

#         return filename

#     except (UnidentifiedImageError, ValueError, Image.DecompressionBombError) as e:
#         raise InvalidImageException(
#             "Uploaded file is corrupted or not a valid image format.",
#             f"Uploaded file is corrupted or not a valid image format: {e}",
#         )


from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from .exceptions import InvalidImageException

Image.MAX_IMAGE_PIXELS = 25_000_000  # Max ~25 Megapixels (approx. 5000x5000)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB strict limit

def process_image(content: bytes) -> bytes:
    """
    Synchronous, CPU-bound image processing function.
    Resizes property photos and returns the optimized WEBP bytes.
    DOES NOT handle saving to disk or cloud.
    """
    # 1. Guard against memory exhaustion attacks
    if len(content) > MAX_FILE_SIZE:
        raise InvalidImageException(
            "File size exceeds the maximum limit of 10MB.",
            f"File size is {len(content)} bytes",
        )

    try:
        # 2. Open image inside context manager safely
        with Image.open(BytesIO(content)) as original:
            # Auto-orient based on camera EXIF data
            img = ImageOps.exif_transpose(original)

            # Ensure image is in RGB mode
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")

            # Preserve aspect ratio within bounding box
            img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

            # 3. Save to an IN-MEMORY buffer instead of the file system
            output_buffer = BytesIO()
            img.save(output_buffer, format="WEBP", quality=80, optimize=True, lossless=False)

            # 4. Return the raw bytes
            return output_buffer.getvalue()

    except (UnidentifiedImageError, ValueError, Image.DecompressionBombError) as e:
        raise InvalidImageException(
            "Uploaded file is corrupted or not a valid image format.",
            f"Uploaded file is corrupted or not a valid image format: {e}",
        )