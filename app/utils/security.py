import jwt
from dotenv import load_dotenv
import os
load_dotenv()

def decode_jwt_unsafe(token: str) -> dict | None:
    """
    Decodes a JWT WITHOUT verifying expiry — used only for rate-limit
    identity resolution. Never used for actual authentication;
    real get_current_guest/get_current_user dependencies still do full,
    correct verification independently.
    """
    try:
        return jwt.decode(
            token,
            os.getenv("SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM")],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        return None