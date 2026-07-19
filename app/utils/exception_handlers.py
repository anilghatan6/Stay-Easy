import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.utils.exceptions import AppBaseException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

app = FastAPI()


# ── 1. Your custom exceptions ─────────────────────────────────
@app.exception_handler(AppBaseException)
async def handle_app_exception(request: Request, exc: AppBaseException):
    logger.info(
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


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
):
    logger.warning(
        "[RequestValidationError] path=%s | errors=%s",
        request.url.path,
        exc.errors(),
    )

    first_error = exc.errors()[0]

    # 1. Intercept malformed JSON syntax errors explicitly
    if first_error.get("type") == "json_invalid":
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid JSON payload format."},
        )

    # 2. Extract field name from the location tuple and format it cleanly
    # e.g., ('body', 'hotel_detail', 'total_rooms') -> "Total Rooms"
    loc = first_error.get("loc", ())
    if loc and len(loc) > 1:
        # Get the last item (the actual field), replace underscores, and capitalize words
        field_name = str(loc[-1]).replace("_", " ").title()
    else:
        field_name = "Input "

    # 3. Handle custom readable messages based on error types
    error_type = first_error.get("type", "")
    ctx = first_error.get("ctx", {})

    if error_type == "greater_than_equal":
        message = f"{field_name} should be greater than or equal to {ctx.get('ge')}"
    elif error_type == "less_than_equal":
        message = f"{field_name} should be less than or equal to {ctx.get('le')}"
    elif error_type == "string_too_short":
        message = (
            f"{field_name} must be at least {ctx.get('min_length')} characters long"
        )
    elif error_type == "missing":
        message = f"{field_name} is required"
    elif error_type == "value_error":
        message = first_error["msg"].replace("Value error, ", "")
    else:
        # Fallback for other standard errors
        raw_msg = first_error["msg"].replace("Value error, ", "")
        # Remove default generic prefix if it's there
        if raw_msg.startswith("Input should be "):
            message = f"{field_name} must be {raw_msg.replace('Input should be ', '')}"
        else:
            message = f"{field_name}: {raw_msg}"

    return JSONResponse(
        status_code=422,
        content={"success": False, "error": message},
    )


# ── 3. Pydantic ValidationError (raised inside your code, not from request) ──
@app.exception_handler(ValidationError)
async def handle_pydantic_validation_error(request: Request, exc: ValidationError):
    # This fires when you manually call a Pydantic model inside a service
    # and it fails — it's an internal issue, so treat it like a 500
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


# ── 4. FastAPI's own HTTPException ────────────────────────────────
@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    # Log 5xx but not 4xx — 4xx are expected client errors
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
@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError):
    logger.warning(
        "[IntegrityError] %s | path=%s",
        str(exc),
        request.url.path,
    )
    # Extract useful part of the error if possible (e.g. duplicate key)
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


# ── 5. Catch-all safety net ───────────────────────────────────────
@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
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
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(Exception, handle_unexpected_exception)
