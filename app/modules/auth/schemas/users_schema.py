from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, Annotated
import re
import uuid


class UserBase(BaseModel):
    full_name: Annotated[str, Field(..., min_length=2, max_length=50, title="Full Name", description="Full name of the user")]
    email: EmailStr
    phone: Annotated[Optional[str], Field(default=None, min_length=10, max_length=15, title="Phone", description="Phone number of the user")]

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not re.match(r"^[a-zA-Z\s]+$", value):
            raise ValueError("Name must contain only alphabetic characters and spaces")
        return value
        

    @field_validator("email", mode="before")
    @classmethod
    def pre_strip_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class UserCreate(UserBase):
    password: Annotated[str, Field(..., min_length=8, max_length=255, title="Password", description="Password of the user")]

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        if not any(char.isdigit() for char in value):
            raise ValueError(
                "Password must contain at least one numerical digit (0-9)."
            )

        # Regex scans for standard special punctuation symbols
        special_char_regex = re.compile(r"[!@#$%^&*(),.?\":{}|<>_+\-=~`[\]\\]")
        if not special_char_regex.search(value):
            raise ValueError("Password must contain at least one special character.")

        # password should not include the spaces in between or before or after
        value = value.strip()
        if " " in value:
            raise ValueError("Password must not contain spaces between the words.")

        return value


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    created_at: datetime
