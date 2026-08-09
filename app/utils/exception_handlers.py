import traceback
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


from app.utils.exceptions import AppBaseException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


# ── Validation error lookup table ─────────────────────────────────────────────
# Maps Pydantic v2 error types → user-friendly message builders.
# To support a new field type or constraint, just add an entry here.
_VALIDATION_MESSAGES: dict[str, Callable[[str, dict], str]] = {
    "missing":                    lambda f, _: f"{f} is required",
    "greater_than_equal":         lambda f, c: f"{f} should be at least {c.get('ge')}",
    "less_than_equal":            lambda f, c: f"{f} should be at most {c.get('le')}",
    "greater_than":               lambda f, c: f"{f} should be greater than {c.get('gt')}",
    "less_than":                  lambda f, c: f"{f} should be less than {c.get('lt')}",
    "string_too_short":           lambda f, c: f"{f} must be at least {c.get('min_length')} characters long",
    "string_too_long":            lambda f, c: f"{f} must be at most {c.get('max_length')} characters long",
    "date_from_datetime_parsing": lambda f, _: f"{f} must be a valid date (e.g. 2026-08-15)",
    "date_parsing":               lambda f, _: f"{f} must be a valid date (e.g. 2026-08-15)",
    "datetime_parsing":           lambda f, _: f"{f} must be a valid date (e.g. 2026-08-15)",
    "int_parsing":                lambda f, _: f"{f} must be a valid integer",
    "int_type":                   lambda f, _: f"{f} must be a valid integer",
    "float_parsing":              lambda f, _: f"{f} must be a valid number",
    "bool_parsing":               lambda f, _: f"{f} must be true or false",
    "uuid_parsing":               lambda f, _: f"{f} must be a valid UUID",
    "list_type":                  lambda f, _: f"{f} must be a list",
    "too_short":                  lambda f, c: f"{f} must have at least {c.get('min_length')} item(s)",
    "too_long":                   lambda f, c: f"{f} must have at most {c.get('max_length')} item(s)",
}


def _format_validation_error(error: dict) -> str:
    """Converts a single Pydantic v2 error dict into a clean user-facing string."""
    loc = error.get("loc", ())
    field = str(loc[-1]).replace("_", " ").title() if len(loc) > 1 else ""
    error_type = error.get("type", "")
    ctx = error.get("ctx", {})

    formatter = _VALIDATION_MESSAGES.get(error_type)
    if formatter:
        return formatter(field, ctx)

    # Fallback: strip Pydantic internals and produce something readable
    raw = error.get("msg", "").replace("Value error, ", "")
    if raw.startswith("Input should be "):
        return f"{field} must be {raw.removeprefix('Input should be ')}"
    return f"{field}: {raw}"


# ── 1. Your custom exceptions ─────────────────────────────────
async def handle_app_exception(request: Request, exc: AppBaseException):

    status_code = int(exc.status_code)
    
    # Check if the status code falls in the 4xx range (400 to 499)
    if status_code // 100 == 4:
        # Log cleaner message without traceback for client errors
        logger.info(
            "[%s] %s | path=%s",
            exc.__class__.__name__,
            exc.internal_detail,
            request.url.path,
        )
    else:
        # Keep traceback for server errors (5xx) or other anomalies
        logger.error(
            "[%s] %s | path=%s\n%s",
            exc.__class__.__name__,
            exc.internal_detail,
            request.url.path,
            traceback.format_exc(),
        )

    return JSONResponse(
        status_code=int(exc.status_code),
        content={"success": False, "error": exc.user_message},
    )


# ── 2. Request validation errors (query/body/path) ─────────────
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
):
    logger.warning(
        "[RequestValidationError] path=%s | errors=%s",
        request.url.path,
        exc.errors(),
    )

    first_error = exc.errors()[0]

    if first_error.get("type") == "json_invalid":
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON payload format."},
        )

    return JSONResponse(
        status_code=422,
        content={"success": False, "error": _format_validation_error(first_error)},
    )



# ── 3. Pydantic ValidationError (raised inside your code, not from request) ──
async def handle_pydantic_validation_error(request: Request, exc: ValidationError):
    logger.error(
        "[PydanticValidationError] path=%s | errors=%s\n%s",
        request.url.path,
        exc.errors(),
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "An internal data error occurred."},
    )


# ── 4. HTTPException — registered on Starlette's base class so it also ──────
#      catches errors raised by the framework itself (404, 405, etc.),
#      not just fastapi.HTTPException (which is a subclass of this).
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 500:
        logger.error(
            "[HTTPException] status=%s detail=%s | path=%s",
            exc.status_code,
            exc.detail,
            request.url.path,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )


# ── 5. Database Integrity Error (Conflicts / FK failures) ──────────
async def handle_integrity_error(request: Request, exc: IntegrityError):
    logger.warning(
        "[IntegrityError] %s | path=%s",
        str(exc),
        request.url.path,
    )
    error_msg = (
        "A database conflict occurred (e.g. duplicate entry or invalid reference)."
    )
    if "UNIQUE constraint failed" in str(exc):
        error_msg = "An entry with this name or unique identifier already exists."
    elif "FOREIGN KEY constraint failed" in str(exc):
        error_msg = "Invalid reference: one of the related records does not exist."

    return JSONResponse(
        status_code=400,
        content={"success": False, "error": error_msg},
    )


# ── 6. Catch-all safety net handler ───────────────────────────────────────────
async def handle_unhandled_exception(request: Request, exc: Exception):
    logger.critical(
        "[UnhandledException] %s | path=%s\n%s",
        str(exc),
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred. Please contact support.",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppBaseException, handle_app_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(ValidationError, handle_pydantic_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(Exception, handle_unhandled_exception)
