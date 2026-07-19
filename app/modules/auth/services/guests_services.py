from fastapi import BackgroundTasks

from app.modules.auth.repositories.guests_repo import GuestRepository
from app.modules.auth.models.guests_model import Guest
from app.modules.auth.services.auth_services import AuthService
from app.utils.exceptions import (
    ServiceException,
    UserAlreadyExistsException,
    UserNotFoundException,
    RepositoryException,
    AccountInactiveException,
    InvalidOTPException,
    AccountActiveException,
    UnauthorizedException,
)
from app.utils.logging import LoggerFactory
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.mail_services import send_verification_email

logger = LoggerFactory.get_logger(__name__)


class GuestService:
    def __init__(
        self,
        guest_repository: GuestRepository,
        auth_service: AuthService,
        otp_service: OTPService,
        background_tasks: BackgroundTasks,
    ):
        self.guest_repository = guest_repository
        self.auth_service = auth_service
        self.otp_service = otp_service
        self.background_tasks = background_tasks

    async def register_guest(self, guest_data: dict) -> Guest:
        """
        Public method to register a guest. It initiates the verification process.
        """
        logger.info(
            f"[GuestService] Registration initiated for: {guest_data.get('email')}"
        )
        try:
            existing_guest = await self.guest_repository.get_guest_by_email(
                guest_data["email"]
            )

            if existing_guest:
                if existing_guest.is_active:
                    raise UserAlreadyExistsException(
                        f"Guest with email {guest_data['email']} already exists and is active"
                    )
                return await self._handle_inactive_guest(existing_guest, guest_data)

            return await self._create_new_guest(guest_data)

        except (UserAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[GuestService] Unexpected error in register_guest: {str(e)}")
            raise ServiceException(str(e))

    async def _handle_inactive_guest(self, guest: Guest, new_data: dict) -> Guest:
        """Helper to reactivate/update an existing but unverified guest."""
        logger.info(f"[GuestService] Updating inactive guest: {guest.email}")
        guest.full_name = new_data["full_name"]
        guest.phone = new_data.get("phone")
        guest.nationality = new_data.get("nationality")
        guest.password_hash = self.auth_service.get_password_hash(new_data["password"])

        updated_guest = await self.guest_repository.update_guest(guest)
        await self._send_verification_otp(updated_guest.email)
        return updated_guest

    async def _create_new_guest(self, guest_data: dict) -> Guest:
        """Helper to create a fresh inactive guest record."""
        logger.info(f"[GuestService] Creating new guest record: {guest_data['email']}")
        guest_data["password_hash"] = self.auth_service.get_password_hash(
            guest_data.pop("password")
        )

        new_guest = await self.guest_repository.register_guest(guest_data)
        await self._send_verification_otp(new_guest.email)
        return new_guest

    async def _send_verification_otp(self, email: str) -> None:
        """Generates and sends an OTP via background tasks."""
        otp = self.otp_service.generate_otp()
        await self.otp_service.set_otp(email, otp)
        self.background_tasks.add_task(send_verification_email, email, otp)
        logger.info(f"[GuestService] Verification OTP triggered for {email}")

    async def verify_registration_otp(self, email: str, otp: str) -> dict:
        """Verifies the OTP and activates the guest."""
        logger.info(f"[GuestService] Verifying OTP for guest: {email}")
        try:
            guest = await self.guest_repository.get_guest_by_email(email)
            if not guest:
                raise UserNotFoundException(
                    "Guest not found", f"Guest {email} not found"
                )

            if not await self.otp_service.verify_otp(email, otp):
                raise InvalidOTPException(
                    "Invalid or expired OTP", f"Invalid or expired OTP for {email}"
                )

            await self.otp_service.delete_otp(email)
            guest.is_active = True
            await self.guest_repository.update_guest(guest)

           
            return {
               "status":"success",
               "message":"Account Verified Successfully"
            }
        except (UserNotFoundException, InvalidOTPException):
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in verify_registration_otp: {str(e)}")
            raise ServiceException(str(e))

    async def resend_registration_otp(self, email: str) -> bool:
        """Resends the registration OTP if the guest is not yet active."""
        logger.info(f"[GuestService] Resending OTP for: {email}")
        try:
            guest = await self.guest_repository.get_guest_by_email(email)
            if not guest:
                raise UserNotFoundException(
                    "Guest not found", f"Guest {email} not found"
                )

            if guest.is_active:
                raise AccountActiveException(
                    "Guest is already active", f"Guest {email} is already active"
                )

            await self._send_verification_otp(email)
            return True
        except (
            UserNotFoundException,
            UserAlreadyExistsException,
            AccountActiveException,
        ):
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in resend_registration_otp: {str(e)}")
            raise ServiceException(str(e))

    async def login_guest(self, credentials: dict) -> dict:
        logger.info(f"[GuestService] Login attempt: {credentials['email']}")
        try:
            guest = await self.guest_repository.get_guest_by_email(credentials["email"])
            if not guest or not self.auth_service.verify_password(
                credentials["password"], guest.password_hash
            ):
                raise UserNotFoundException(
                    "Invalid credentials", "Email/Password mismatch"
                )

            if not guest.is_active:
                raise AccountInactiveException(
                    "Account not verified. Please verify your email."
                )

            token_data = {"sub": str(guest.id), "role": "guest"}
            return {
                "access_token": self.auth_service.create_access_token(token_data),
                "refresh_token": self.auth_service.create_refresh_token(token_data),
                "token_type": "bearer",
            }
        except (UserNotFoundException, ServiceException, AccountInactiveException):
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in login_guest: {str(e)}")
            raise ServiceException(str(e))

    async def get_guest_by_email(self, email: str) -> Guest:
        logger.info(f"[GuestService] Fetching guest: {email}")
        try:
            guest = await self.guest_repository.get_guest_by_email(email)
            if not guest:
                raise UserNotFoundException(
                    "Guest not found", f"Guest {email} not found"
                )
            return guest
        except UserNotFoundException:
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in get_guest_by_email: {str(e)}")
            raise ServiceException(str(e))

    async def get_guest_by_id(self, guest_id: str) -> Guest:
        logger.info(f"[GuestService] Fetching guest by ID: {guest_id}")
        try:
            guest = await self.guest_repository.get_guest_by_id(guest_id)
            if not guest:
                raise UserNotFoundException(
                    "Guest not found", f"ID {guest_id} not found"
                )
            return guest
        except UserNotFoundException:
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in get_guest_by_id: {str(e)}")
            raise ServiceException(str(e))

    async def refresh_token(self, refresh_token: str) -> dict:
        logger.info("[GuestService] Refreshing tokens")
        try:
            payload = self.auth_service.verify_refresh_token(refresh_token)
            if not payload:
                raise UnauthorizedException("Invalid refresh token")

            token_data = {"sub": str(payload["user_id"]), "role": "guest"}
            return {
                "access_token": self.auth_service.create_access_token(token_data),
                "token_type": "bearer",
            }
        except UnauthorizedException:
            raise
        except Exception as e:
            logger.error(f"[GuestService] Error in refresh_token: {str(e)}")
            raise ServiceException("Token refresh failed")
