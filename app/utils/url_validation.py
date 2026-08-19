# # app/utils/url_validation.py

from app.config.settings_config import settings
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


def validate_khalti_return_url(url: str) -> str:
    """
    Ensures the return_url starts with the configured KHALTI_RETURN_URL_BASE or KHALTI_RETURN_URL.
    Returns the url unchanged if valid, raises ValueError otherwise.
    """
    base = (
      settings.KHALTI_RETURN_URL
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



# from urllib.parse import urlparse
# from typing import Optional
# from app.config.settings_config import settings
# from app.utils.logging import LoggerFactory
# from app.utils.exceptions import InvalidReturnUrl

# logger = LoggerFactory.get_logger(__name__)


# def resolve_khalti_return_url(request_origin: Optional[str]) -> str:
#     """
#     Picks the correct KHALTI_RETURN_URL from the allowed list based on the
#     request's Origin header. The Origin only SELECTS among server-configured
#     values — it never supplies the URL itself, so this stays safe even though
#     Origin is client-controlled.
#     """
#     allowed_urls = settings.KHALTI_RETURN_URL  # e.g. [localhost url, vercel url]

#     if not allowed_urls:
#         logger.error("[URLValidation] KHALTI_RETURN_URL is not configured in environment")
#         raise ValueError("KHALTI_RETURN_URL is not configured on the server")

#     if not request_origin:
#         # No Origin header (server-to-server call, curl, etc.) — fall back to first configured url
#         logger.warning("[URLValidation] No Origin header present, falling back to default return url")
#         return allowed_urls[0]

#     request_origin = request_origin.rstrip("/")

#     for candidate in allowed_urls:
#         candidate_origin = f"{urlparse(candidate).scheme}://{urlparse(candidate).netloc}"
#         if candidate_origin == request_origin:
#             return candidate

#     logger.warning(
#         f"[URLValidation] Origin '{request_origin}' did not match any allowed base {allowed_urls}, "
#     )
#     raise InvalidReturnUrl("Invalid return url")
