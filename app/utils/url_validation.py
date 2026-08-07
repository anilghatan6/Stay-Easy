# app/utils/url_validation.py

import os
from dotenv import load_dotenv
from app.utils.logging import LoggerFactory

load_dotenv()
logger = LoggerFactory.get_logger(__name__)


def validate_khalti_return_url(url: str) -> str:
    """
    Ensures the return_url starts with the configured KHALTI_RETURN_URL_BASE or KHALTI_RETURN_URL.
    Returns the url unchanged if valid, raises ValueError otherwise.
    """
    base = (
        os.getenv("KHALTI_RETURN_URL_BASE") or os.getenv("KHALTI_RETURN_URL") or ""
    ).rstrip("/")

    if not base:
        logger.error(
            "[URLValidation] Neither KHALTI_RETURN_URL_BASE nor KHALTI_RETURN_URL is configured in environment"
        )
        raise ValueError("KHALTI_RETURN_URL is not configured on the server")

    if not url or not url.startswith(base):
        logger.warning(
            f"[URLValidation] Rejected return_url not matching base '{base}': {url}"
        )
        raise ValueError("Invalid Return URL")

    return url
