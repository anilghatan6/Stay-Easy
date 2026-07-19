from fastapi import BackgroundTasks
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.models.users_model import User
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.services.otp_service import OTPService
from app.modules.auth.services.mail_services import send_verification_email

from app.utils.exceptions import (
    ServiceException,
    UserAlreadyExistsException,
    UserNotFoundException,
    RepositoryException,
    InvalidRefreshTokenException,
    AccountInactiveException,
    AccountActiveException,
    InvalidOTPException,
    UnauthorizedException,
)
from app.utils.logging import LoggerFactory
import uuid

logger = LoggerFactory.get_logger(__name__)


class UserService:
    def __init__(
        self,
        user_repository: UserRepository,
        auth_service: AuthService,
        otp_service: OTPService,
        background_tasks: BackgroundTasks,
    ):
        self.user_repository = user_repository
        self.auth_service = auth_service
        self.otp_service = otp_service
        self.background_tasks = background_tasks

    async def register_user(self, user_data: dict) -> User:
        """
        Public method to register a user. It initiates the verification process.
        """
        logger.info(
            f"[UserService] Registration initiated for: {user_data.get('email')}"
        )
        try:
            existing_user = await self.user_repository.get_user_by_email(
                user_data.get("email")
            )

            if existing_user:
                if existing_user.is_active:
                    raise UserAlreadyExistsException(
                        f"User with email {user_data['email']} already exists and is active"
                    )
                return await self._handle_inactive_user(existing_user, user_data)

            return await self._create_new_user(user_data)

        except (UserAlreadyExistsException, RepositoryException):
            raise
        except Exception as e:
            logger.error(f"[UserService] Unexpected error in register_user: {str(e)}")
            raise ServiceException(str(e))

    async def _handle_inactive_user(self, user: User, new_data: dict) -> User:
        """Helper to reactivate/update an existing but unverified user."""
        logger.info(f"[UserService] Updating inactive user: {user.email}")
        user.full_name = new_data["full_name"]
        user.phone = new_data.get("phone")
        user.hashed_password = self.auth_service.get_password_hash(new_data["password"])
        user.role = "admin"
        try:
            updated_user = await self.user_repository.update_user(user)
            await self._send_verification_otp(updated_user.email)
            return updated_user
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in handle_inactive_user: {str(e)}")
            raise ServiceException(str(e))

    async def _create_new_user(self, user_data: dict) -> User:
        """Helper to create a fresh inactive user record."""
        logger.info(f"[UserService] Creating new user record: {user_data['email']}")
        user_data["hashed_password"] = self.auth_service.get_password_hash(
            user_data.pop("password")
        )
        user_data["role"] = "admin"

        try:
            new_user = await self.user_repository.register_user(user_data)
            await self._send_verification_otp(new_user.email)
            return new_user
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in create_new_user: {str(e)}")
            raise ServiceException(str(e))

    async def _send_verification_otp(self, email: str) -> None:
        """Generates and sends an OTP via background tasks."""
        otp = self.otp_service.generate_otp()
        await self.otp_service.set_otp(email, otp)
        self.background_tasks.add_task(send_verification_email, email, otp)
        logger.info(f"[UserService] Verification OTP triggered for {email}")

    async def verify_registration_otp(self, email: str, otp: str) -> dict:
        """Verifies the OTP and activates the user."""
        logger.info(f"[UserService] Verifying OTP for user: {email}")
        try:
            user = await self.user_repository.get_user_by_email(email)
            if not user:
                raise UserNotFoundException("User not found", f"User {email} not found")

            if not await self.otp_service.verify_otp(email, otp):
                raise InvalidOTPException(
                    "Invalid or expired OTP", f"Invalid or expired OTP for {email}"
                )

            await self.otp_service.delete_otp(email)
            user.is_active = True
            await self.user_repository.update_user(user)

            return {"status": "success", "message": "Account Verified Successfully"}
        except (UserNotFoundException, InvalidOTPException):
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in verify_registration_otp: {str(e)}")
            raise ServiceException(str(e))

    async def resend_registration_otp(self, email: str) -> bool:
        """Resends the registration OTP if the user is not yet active."""
        logger.info(f"[UserService] Resending OTP for: {email}")
        try:
            user = await self.user_repository.get_user_by_email(email)
            if not user:
                raise UserNotFoundException("User not found", f"User {email} not found")

            if user.is_active:
                raise AccountActiveException(
                    "User is already active", f"User {email} is already active"
                )

            await self._send_verification_otp(email)
            return True
        except (UserNotFoundException, AccountActiveException):
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in resend_registration_otp: {str(e)}")
            raise ServiceException(str(e))

    async def login_user(self, credentials: dict) -> dict:
        logger.info(f"[UserService] Login attempt: {credentials['email']}")
        try:
            email = credentials["email"].strip()
            password = credentials["password"].strip()
            user = await self.user_repository.get_user_by_email(email)
            if not user or not self.auth_service.verify_password(
                password, user.hashed_password
            ):
                raise UserNotFoundException(
                    "Invalid credentials", "Incorrect email or password"
                )

            if not user.is_active:
                raise AccountInactiveException(
                    "Account not verified. Please verify your email."
                )

            token_data = {"sub": str(user.id), "role": user.role}
            return {
                "access_token": self.auth_service.create_access_token(token_data),
                "refresh_token": self.auth_service.create_refresh_token(token_data),
                "token_type": "bearer",
            }
        except (UserNotFoundException, AccountInactiveException):
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in login_user: {str(e)}")
            raise ServiceException(str(e))

    async def get_user_by_email(self, email: str) -> User:
        logger.info(f"[UserService] Fetching user: {email}")
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise UserNotFoundException("User not found", f"User {email} not found")
        return user

    async def get_user_by_id(self, user_id: str) -> User:
        logger.info(f"[UserService] Fetching user by ID: {user_id}")
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException("User not found", f"ID {user_id} not found")
        return user

    async def refresh_token(self, refresh_token: str) -> dict:
        logger.info("[UserService] Refreshing tokens")
        try:
            payload = self.auth_service.verify_refresh_token(refresh_token)
            if not payload:
                raise UnauthorizedException("Invalid refresh token")

            token_data = {"sub": str(payload["user_id"]), "role": payload["role"]}
            return {
                "access_token": self.auth_service.create_access_token(token_data),
                "token_type": "bearer",
            }
        except InvalidRefreshTokenException:
            raise
        except Exception as e:
            logger.error(f"[UserService] Error in refresh_token: {str(e)}")
            raise ServiceException("Token refresh failed")

    async def update_user_tenant_id(self, user_id: str, tenant_id: uuid.UUID) -> bool:
        logger.info(f"[UserService] Mapping user {user_id} to tenant {tenant_id}")
        try:
            user = await self.get_user_by_id(user_id)
            user.tenant_id = tenant_id
            await self.user_repository.update_user(user)
            return True
        except Exception as e:
            logger.error(f"[UserService] Error in update_user_tenant_id: {str(e)}")
            raise ServiceException("Tenant update failed")
