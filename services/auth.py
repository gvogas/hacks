import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException

from services import db

_BCRYPT_MAX = 72  # bcrypt truncates beyond this

JWT_ALG = "HS256"
JWT_TTL_DAYS = 30
_SECRET_FILE = ".jwt_secret"


def _load_secret() -> str:
    env = os.getenv("JWT_SECRET")
    if env:
        return env
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE) as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(48)
    with open(_SECRET_FILE, "w") as f:
        f.write(secret)
    return secret


_SECRET = _load_secret()


def hash_password(pw: str) -> str:
    pw_bytes = pw.encode("utf-8")[:_BCRYPT_MAX]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:_BCRYPT_MAX], pw_hash.encode("utf-8"))
    except Exception:
        return False


def make_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, _SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _SECRET, algorithms=[JWT_ALG])


def create_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    if db.query_one("SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(status_code=409, detail="Email already registered")
    cur = db.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email, hash_password(password), datetime.utcnow().isoformat()),
    )
    return {"id": cur.lastrowid, "email": email}


def authenticate(email: str, password: str) -> dict:
    row = db.query_one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"id": row["id"], "email": row["email"]}


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = int(payload["sub"])
    row = db.query_one("SELECT id, email FROM users WHERE id = ?", (user_id,))
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": row["id"], "email": row["email"]}


CurrentUser = Depends(current_user)
