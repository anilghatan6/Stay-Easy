from pydantic import BaseModel, EmailStr, Field

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str= Field(..., min_length=6, max_length=6, title="OTP", description="OTP received via email")

class ResendOTP(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str