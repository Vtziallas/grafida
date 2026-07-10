import time

import bcrypt
import jwt

from app.config import settings


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) + settings.jwt_expires_minutes * 60},
        settings.jwt_secret, algorithm="HS256")


def decode_token(t: str) -> int:
    return int(jwt.decode(t, settings.jwt_secret, algorithms=["HS256"])["sub"])
