from redis.asyncio import Redis
import secrets
from app.utils.logging import LoggerFactory
from app.utils.exceptions import ServiceException
from dotenv import load_dotenv
import os

load_dotenv()

logger = LoggerFactory.get_logger(__name__)


class OTPService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ttl = int(os.getenv("OTP_EXPIRATION_SECONDS"))

    def _generate_key(self, email: str) -> str:
        """Standardizes the Redis key format for multi-tenant safety."""
        return f"auth:otp:{email.lower()}"

    async def set_otp(self, email: str, otp_code: str) -> None:
        """
        Saves the OTP with a strict expiration timer.
        Using SETEX handles both saving and setting the TTL atomically.
        """
        key = self._generate_key(email)
        try:
            await self.redis.set(name=key, value=otp_code, ex=self.ttl)
        except Exception as e:
            logger.error(f"[OTPService] Error setting OTP: {str(e)}")
            raise ServiceException(str(e))

    async def get_otp(self, email: str) -> str | None:
        """
        Retrieves the OTP. Returns None if it doesn't exist or expired.
        """
        key = self._generate_key(email)
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.error(f"[OTPService] Error getting OTP: {str(e)}")
            raise ServiceException(str(e))

    async def delete_otp(self, email: str) -> None:
        """
        Instantly destroys the OTP. Must be called immediately after successful verification.
        """
        key = self._generate_key(email)
        try:
            await self.redis.delete(key)
            logger.info(f"[OTPService] OTP deleted successfully for email {email}")
        except Exception as e:
            logger.error(f"[OTPService] Error deleting OTP: {str(e)}")
            raise ServiceException(str(e))

    async def update_otp(self, email: str, new_otp_code: str) -> None:
        """
        For the 'Resend OTP' flow.
        In Redis, updating is exactly the same as setting. Overwriting the key
        automatically resets the 10-minute expiration timer to full.
        """
        try:
            await self.set_otp(email, new_otp_code)
            logger.info(f"[OTPService] OTP updated successfully for email {email}")
        except Exception as e:
            logger.error(f"[OTPService] Error updating OTP: {str(e)}")
            raise ServiceException(str(e))

    def generate_otp(self) -> str:
        """
        Generates a 6-digit OTP.
        """
        otp = "".join(secrets.choice("0123456789") for _ in range(6))
        logger.info(f"[OTPService] OTP generated successfully: {otp}")
        return otp

    async def verify_otp(self, email: str, otp_code: str) -> bool:
        """
        Verifies the OTP.
        """
        is_dev = os.getenv("ENVIRONMENT") == "development"
        master_otp = os.getenv("DEVELOPMENT_MASTER_OTP", "123456")

        if is_dev and otp_code == master_otp:
            logger.info(f"[OTPService][DEV MODE] Master OTP used successfully for {email}")
            # Optionally delete the real OTP from Redis if it exists
            await self.delete_otp(email)
            return True

    # 2. Standard production validation logic
        try:
            stored_otp = await self.get_otp(email)
            if not stored_otp:
                logger.error(f"[OTPService] OTP not found for email {email}")
                return False
            elif stored_otp == otp_code:
                logger.info(f"[OTPService] OTP verified successfully for email {email}")
                return True
            else:
                logger.error(f"[OTPService] Invalid OTP for email {email}")
                return False
        except Exception as e:
            logger.error(f"[OTPService] Error verifying OTP: {str(e)}")
            raise ServiceException(str(e))
