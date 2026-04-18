import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import db

_BCRYPT_MAX = 72  # bcrypt silently truncates beyond this
JWT_ALG = "HS256"
JWT_TTL_DAYS = 30
_SECRET_FILE = ".jwt_secret"
_bearer = HTTPBearer(auto_error=False)


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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:_BCRYPT_MAX], bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:_BCRYPT_MAX], pw_hash.encode("utf-8"))
    except Exception:
        return False


def make_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": now_utc() + timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, _SECRET, algorithm=JWT_ALG)


def make_ephemeral_token(payload: dict, ttl_minutes: int = 10) -> str:
    payload = {**payload, "exp": now_utc() + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, _SECRET, algorithm=JWT_ALG)


def decode_ephemeral_token(token: str) -> dict:
    return jwt.decode(token, _SECRET, algorithms=[JWT_ALG])


def issue_session(user: dict) -> dict:
    return {"token": make_token(user["id"], user["email"]), "user": user}


def create_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, hash_password(password), now_utc().isoformat()),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"id": cur.lastrowid, "email": email}


def authenticate(email: str, password: str) -> dict:
    row = db.query_one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"id": row["id"], "email": row["email"]}


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, _SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    row = db.query_one("SELECT id, email FROM users WHERE id = ?", (int(payload["sub"]),))
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": row["id"], "email": row["email"]}


CurrentUser = Depends(current_user)
