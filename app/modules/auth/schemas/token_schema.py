from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str= Field(..., min_length=6, max_length=6, title="OTP", description="OTP received via email")

class ResendOTP(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    must_change_password: bool
    role: str
    property: Optional[Dict[str, Any]] = None
    properties: Optional[list[Dict[str, Any]]] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str

