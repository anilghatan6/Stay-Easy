from pydantic import model_validator
from pydantic import BaseModel, EmailStr, Field, AfterValidator,field_validator
import re
from typing import Annotated


def check_password_rules(value: str) -> str:
    value = value.strip()
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one numerical digit (0-9).")

    special_char_regex = re.compile(r"[!@#$%^&*(),.?\":{}|<>_+\-=~`[\]\\]")
    if not special_char_regex.search(value):
        raise ValueError("Password must contain at least one special character.")

    if " " in value:
        raise ValueError("Password must not contain spaces between the words.")
    return value


StrongPassword = Annotated[
    str, Field(min_length=8), AfterValidator(check_password_rules)
]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: StrongPassword


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: StrongPassword
    
    @model_validator(mode="after")
    def validate_not_same_current_and_new_password(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("Current password and new password cannot be the same.")
        return self
