class AppBaseException(Exception):
    """
    Base class for all custom application exceptions.
    """

    def __init__(
        self, user_message: str, internal_detail: str = None, status_code: int = 500
    ):
        self.user_message = user_message  # shown to API consumer
        self.internal_detail = internal_detail  # only logged internally
        self.status_code = status_code
        super().__init__(internal_detail or user_message)


class RepositoryException(AppBaseException):
    """Raised when database/repository operations fail."""

    def __init__(
        self,
        internal_detail: str = None,
        status_code: int = 500,
    ):
        super().__init__(
            user_message="A database error occurred. Please try again later.",
            internal_detail=internal_detail,
            status_code=status_code,
        )


class ServiceException(AppBaseException):
    """Raised when business logic fails unexpectedly."""

    def __init__(
        self,
        internal_detail: str = None,
        status_code: int = 500,
    ):
        super().__init__(
            user_message="An internal error occurred while processing your request.",
            internal_detail=internal_detail,
            status_code=status_code,
        )


class UserAlreadyExistsException(AppBaseException):
    """Raised when a user with the same email already exists."""

    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message, internal_detail=user_message, status_code=409
        )


class AccountInactiveException(AppBaseException):
    """Raised when a user account is inactive."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=400
        )


class AccountActiveException(AppBaseException):
    """Raised when a user account is active."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=400
        )


class InvalidOTPException(AppBaseException):
    """Raised when an OTP is invalid or expired."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=400
        )


class InvalidRefreshTokenException(AppBaseException):
    """Raised when a refresh token is invalid or expired."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=401
        )


class UserNotFoundException(AppBaseException):
    """Raised when a user with the given email is not found."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=400
        )


class TenantAlreadyExistsException(AppBaseException):
    """Raised when a tenant with the same name already exists."""

    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="Tenant already exists",
            internal_detail=internal_detail,
            status_code=400,
        )


class TenantSlugAlreadyExistsException(AppBaseException):
    """Raised when a tenant with the same slug already exists."""

    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="Tenant with this name or slug already exists",
            internal_detail=internal_detail,
            status_code=400,
        )


class TenantNotFoundException(AppBaseException):
    """Raised when a tenant with the given name is not found."""

    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="Tenant not found",
            internal_detail=internal_detail,
            status_code=404,
        )


class PropertyAlreadyExistsException(AppBaseException):
    """Raised when a property with the same name already exists."""

    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=400,
        )


class PropertyNotFoundException(AppBaseException):
    """Raised when a property with the given name is not found."""

    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="Property not found",
            internal_detail=internal_detail,
            status_code=404,
        )


class UnauthorizedException(AppBaseException):
    """Raised when a user is not authorized to perform an action."""

    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="You are not authorized to perform this action",
            internal_detail=internal_detail,
            status_code=401,
        )


class RoomTypeNotFoundException(AppBaseException):
    def __init__(self, internal_detail: str = None):
        super().__init__(
            user_message="Room type not found",
            internal_detail=internal_detail,
            status_code=404,
        )


class ResourceConflictException(AppBaseException):
    """Raised for duplicate entries or constraint violations."""

    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=400
        )


class InvalidImageException(AppBaseException):
    def __init__(
        self, user_message="Invalid image file provided", internal_detail: str = None
    ):
        super().__init__(
            user_message=user_message,
            internal_detail=internal_detail,
            status_code=400,
        )


class DefaultAmenityNotExistsException(AppBaseException):
    """Raised when a default amenity does not exist in the system."""

    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message, internal_detail=user_message, status_code=400
        )


class AmenityNotFoundException(AppBaseException):
    def __init__(self, user_message: str, internal_detail: str = None):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=404
        )


class HotelNotFoundException(AppBaseException):
    """Raised when a hotel with the given ID is not found."""

    def __init__(self, internal_detail: str):
        super().__init__(
            user_message="Hotel not found",
            internal_detail=internal_detail,
            status_code=404,
        )


class RoomNameAlreadyExistsException(AppBaseException):
    def __init__(self, user_message, status_code=400):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=status_code,
        )


class RoomNotFoundException(AppBaseException):
    def __init__(self, user_message="Room not found", internal_detail: str = None):
        super().__init__(
            user_message=user_message,
            internal_detail=internal_detail,
            status_code=404,
        )

class RoomTypeAlreadyExistsException(AppBaseException):
    def __init__(self, user_message, status_code=400):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=status_code,
        )

class BedTypeAlreadyExistsException(AppBaseException):
    def __init__(self, user_message, status_code=400):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=status_code,
        )

class InvalidDateException(AppBaseException):
    def __init__(self, user_message, status_code=400):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=status_code,
        )


class ImageStorageException(AppBaseException):
    def __init__(
        self, user_message: str, internal_detail: str = None, status_code: int = 500
    ):
        super().__init__(
            user_message=user_message,
            internal_detail=internal_detail,
            status_code=status_code,
        )


class OfferNotFoundException(AppBaseException):
    def __init__(self, user_message: str, internal_detail: str):
        super().__init__(
            user_message=user_message, internal_detail=internal_detail, status_code=404
        )


class OfferNameAlreadyExistsException(AppBaseException):
    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message, internal_detail=user_message, status_code=409
        )


class DiscountCodeAlreadyExistException(AppBaseException):
    def __init__(self, user_message:str):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=409
        )


class DiscountCodeNotFoundException(AppBaseException):
    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=404
        )

class DiscountCodeValidationError(AppBaseException):
    def __init__(self, user_message: str):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=400
        )

class DiscountCodeDuplicateException(AppBaseException):
    def __init__(self, user_message:str):
        super().__init__(
            user_message=user_message,
            internal_detail=user_message,
            status_code=409
        )