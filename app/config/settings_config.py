# app/core/config.py

from typing import List,Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    # --- Database & Cache ---
    DATABASE_URL: str
    REDIS_URL: str

    # --- Email (Resend) ---
    RESEND_API_KEY: str
    SENDER_EMAIL: str
    OTP_EXPIRATION_SECONDS: int = 600

    # --- Auth / JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Password reset ---
    FRONTEND_URL: str
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 10
    FRONTEND_LOGIN_URL: str

    # --- Image storage (Cloudinary) ---
    IMAGE_STORAGE_PROVIDER: str = "cloudinary"
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    CLOUDINARY_BASE: str

    # --- CORS ---
    ALLOWED_ORIGINS: Annotated[List[str],NoDecode]

    # --- Booking / locks ---
    SOFT_LOCK_TTL_SECONDS: int = 600

    # --- Payments ---
    STRIPE_SECRET_KEY: str
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    KHALTI_SECRET_KEY: str
    KHALTI_RETURN_URL: Annotated[List[str], NoDecode]
    KHALTI_WEBSITE_URL: str

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_comma_separated_allowed_origins(cls, v):
        if isinstance(v, str):
            return [item.strip().rstrip("/") for item in v.split(",") if item.strip()]
        return v

    @field_validator("KHALTI_RETURN_URL", mode="before")
    @classmethod
    def split_comma_separated(cls, v):
        if isinstance(v, str):
            return [item.strip().rstrip("/") for item in v.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()