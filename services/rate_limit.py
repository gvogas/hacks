import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_or_ip(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return "token:" + auth_header[7:][:64]
    return "ip:" + get_remote_address(request)


limiter = Limiter(key_func=_user_or_ip, default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120/minute")])

AUTH_LIMIT = os.getenv("RATE_LIMIT_AUTH", "5/minute")
UPLOAD_LIMIT = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")
AI_LIMIT = os.getenv("RATE_LIMIT_AI", "10/minute")
SPOTIFY_LIMIT = os.getenv("RATE_LIMIT_SPOTIFY", "60/minute")
