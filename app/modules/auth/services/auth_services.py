from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")

password_hash = PasswordHash.recommended()


class AuthService:
    def get_password_hash(self, password: str) -> str:
        return password_hash.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return password_hash.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_access_token(self, token: str) -> dict | None:
        """Verify a JWT access token and return the subject (user id) if valid."""
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
        except jwt.InvalidTokenError:
            return None
        else:
            return {"user_id": payload.get("sub"), "role": payload.get("role")}

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_refresh_token(self, refresh_token: str) -> dict | None:
        """Verify a JWT refresh token and return the subject (user id) if valid."""
        try:
            payload = jwt.decode(
                refresh_token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
        except jwt.InvalidTokenError:
            return None
        else:
            return {"user_id": payload.get("sub"), "role": payload.get("role")}
