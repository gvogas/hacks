import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import jwt
import requests
from fastapi import HTTPException

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    Fernet = None

    class InvalidToken(Exception):
        pass

from services import auth, db
from services.exceptions import ExternalServiceError

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1"
STATE_TOKEN_TYPE = "spotify_oauth"
STATE_TTL_MINUTES = 10
DEFAULT_SCOPES = (
    "user-read-private",
    "user-read-email",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-modify-playback-state",
    "playlist-read-private",
    "playlist-read-collaborative",
    "streaming",
)
TOKEN_REFRESH_SKEW_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 12
ENCRYPTED_TOKEN_PREFIX = "fernet:"
TOKEN_KEY_FILE = ".spotify_token_key"
_token_cipher = None
_token_key_source: str | None = None


@dataclass(frozen=True, slots=True)
class SpotifySettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...]


def is_configured() -> bool:
    return bool(os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET"))


def get_status(user_id: int) -> dict:
    row = _connection_row(user_id)
    return {
        "configured": is_configured(),
        "connected": row is not None,
        "display_name": row["display_name"] if row else None,
        "spotify_user_id": row["spotify_user_id"] if row else None,
        "scope": row["scope"] if row else "",
    }


def build_authorization(user_id: int) -> dict:
    settings = _settings()
    nonce = secrets.token_urlsafe(24)
    state = auth.make_ephemeral_token(
        {"typ": STATE_TOKEN_TYPE, "sub": str(user_id), "nonce": nonce},
        ttl_minutes=STATE_TTL_MINUTES,
    )
    params = {
        "client_id": settings.client_id,
        "response_type": "code",
        "redirect_uri": settings.redirect_uri,
        "scope": " ".join(settings.scopes),
        "state": state,
    }
    return {"auth_url": f"{AUTHORIZE_URL}?{urlencode(params)}", "nonce": nonce}


def complete_authorization(code: str | None, state: str | None, nonce_cookie: str | None) -> int:
    if not code:
        raise HTTPException(status_code=400, detail="Missing Spotify authorization code")
    payload = _decode_state(state, nonce_cookie)
    user_id = int(payload["sub"])
    settings = _settings()

    token = _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.redirect_uri,
        },
        settings,
    )
    profile = _spotify_request("GET", "/me", token["access_token"])
    _save_connection(user_id, token, profile)
    return user_id


def disconnect(user_id: int) -> dict:
    db.execute("DELETE FROM spotify_connections WHERE user_id = ?", (user_id,))
    return get_status(user_id)


def get_available_devices(user_id: int) -> dict:
    access_token = valid_access_token(user_id)
    return _spotify_request("GET", "/me/player/devices", access_token)


def search_catalog(user_id: int, query: str, limit: int = 8) -> dict:
    access_token = valid_access_token(user_id)
    query = query.strip()
    if not query:
        return {"tracks": [], "playlists": []}

    limit = min(max(int(limit), 1), 20)
    results = _spotify_request(
        "GET",
        "/search",
        access_token,
        params={"q": query, "type": "track,playlist", "limit": limit},
    )
    return {
        "tracks": [_serialize_track(item) for item in (results.get("tracks", {}).get("items") or []) if item],
        "playlists": [_serialize_playlist(item) for item in (results.get("playlists", {}).get("items") or []) if item],
    }


def get_user_playlists(user_id: int, limit: int = 20) -> dict:
    access_token = valid_access_token(user_id)
    limit = min(max(int(limit), 1), 50)
    results = _spotify_request("GET", "/me/playlists", access_token, params={"limit": limit})
    return {
        "playlists": [_serialize_playlist(item) for item in (results.get("items") or []) if item],
        "total": results.get("total", 0),
    }


def get_current_playback(user_id: int) -> dict:
    access_token = valid_access_token(user_id)
    playback = _spotify_request("GET", "/me/player", access_token) or {}
    item = playback.get("item")
    device = playback.get("device") or {}
    context = playback.get("context") or {}
    duration_ms = item.get("duration_ms", 0) if item else 0
    return {
        "is_playing": bool(playback.get("is_playing")),
        "progress_ms": playback.get("progress_ms") or 0,
        "duration_ms": duration_ms,
        "item": _serialize_playback_item(item) if item else None,
        "device": {
            "id": device.get("id"),
            "name": device.get("name"),
            "type": device.get("type"),
        } if device else None,
        "context": {
            "type": context.get("type"),
            "uri": context.get("uri"),
            "external_url": (context.get("external_urls") or {}).get("spotify"),
        } if context else None,
    }


def transfer_playback(user_id: int, device_id: str, play: bool = False) -> dict:
    access_token = valid_access_token(user_id)
    _spotify_request("PUT", "/me/player", access_token, json={"device_ids": [device_id], "play": play})
    return {"ok": True}


def start_or_resume_playback(
    user_id: int,
    context_uri: str | None = None,
    uris: list[str] | None = None,
    device_id: str | None = None,
) -> dict:
    access_token = valid_access_token(user_id)
    body = {}
    if context_uri:
        body["context_uri"] = context_uri
    if uris:
        body["uris"] = uris
    params = {"device_id": device_id} if device_id else None
    _spotify_request("PUT", "/me/player/play", access_token, params=params, json=body or None)
    return {"ok": True}


def pause_playback(user_id: int) -> dict:
    access_token = valid_access_token(user_id)
    _spotify_request("PUT", "/me/player/pause", access_token)
    return {"ok": True}


def next_track(user_id: int) -> dict:
    access_token = valid_access_token(user_id)
    _spotify_request("POST", "/me/player/next", access_token)
    return {"ok": True}


def previous_track(user_id: int) -> dict:
    access_token = valid_access_token(user_id)
    _spotify_request("POST", "/me/player/previous", access_token)
    return {"ok": True}


def valid_access_token(user_id: int) -> str:
    row = _connection_row(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Spotify is not connected")

    access_token = _decrypt_token(row["access_token"])
    refresh_token = _decrypt_token(row["refresh_token"])

    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at > auth.now_utc() + timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS):
        _encrypt_legacy_tokens(user_id, row, access_token, refresh_token)
        return access_token

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Spotify connection expired. Connect Spotify again.")

    settings = _settings()
    token = _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
        settings,
    )
    refresh_token = token.get("refresh_token") or refresh_token
    expires_at = auth.now_utc() + timedelta(seconds=int(token.get("expires_in", 3600)))
    now = auth.now_utc().isoformat()

    db.execute(
        "UPDATE spotify_connections SET access_token = ?, refresh_token = ?, expires_at = ?, "
        "scope = ?, token_type = ?, updated_at = ? WHERE user_id = ?",
        (
            _encrypt_token(token["access_token"]),
            _encrypt_token(refresh_token),
            expires_at.isoformat(),
            token.get("scope", row["scope"]),
            token.get("token_type", row["token_type"]),
            now,
            user_id,
        ),
    )
    return token["access_token"]


def _settings() -> SpotifySettings:
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify is not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.",
        )

    default_redirect = f"http://127.0.0.1:{os.getenv('PORT', '8000')}/api/spotify/callback"
    raw_scopes = os.getenv("SPOTIFY_SCOPES", " ".join(DEFAULT_SCOPES))
    scopes = tuple(scope for scope in raw_scopes.split() if scope)
    return SpotifySettings(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", default_redirect).strip(),
        scopes=scopes or DEFAULT_SCOPES,
    )


def _decode_state(state: str | None, nonce_cookie: str | None) -> dict:
    if not state or not nonce_cookie:
        raise HTTPException(status_code=400, detail="Missing Spotify OAuth state")
    try:
        payload = auth.decode_ephemeral_token(state)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Spotify connection timed out. Try again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid Spotify OAuth state")

    if payload.get("typ") != STATE_TOKEN_TYPE or payload.get("nonce") != nonce_cookie:
        raise HTTPException(status_code=400, detail="Invalid Spotify OAuth state")
    return payload


def _connection_row(user_id: int):
    return db.query_one("SELECT * FROM spotify_connections WHERE user_id = ?", (user_id,))


def _save_connection(user_id: int, token: dict, profile: dict) -> None:
    now = auth.now_utc().isoformat()
    expires_at = auth.now_utc() + timedelta(seconds=int(token.get("expires_in", 3600)))
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "spotify_user_id = excluded.spotify_user_id, display_name = excluded.display_name, "
        "scope = excluded.scope, token_type = excluded.token_type, access_token = excluded.access_token, "
        "refresh_token = COALESCE(excluded.refresh_token, spotify_connections.refresh_token), "
        "expires_at = excluded.expires_at, updated_at = excluded.updated_at",
        (
            user_id,
            profile.get("id"),
            profile.get("display_name") or profile.get("email") or "Spotify user",
            token.get("scope", ""),
            token.get("token_type", "Bearer"),
            _encrypt_token(token["access_token"]),
            _encrypt_token(token.get("refresh_token")),
            expires_at.isoformat(),
            now,
            now,
        ),
    )


def _serialize_track(track: dict) -> dict:
    album = track.get("album") or {}
    artists = track.get("artists") or []
    return {
        "id": track.get("id"),
        "name": track.get("name") or "Untitled track",
        "uri": track.get("uri"),
        "artist": ", ".join(artist.get("name", "") for artist in artists if artist.get("name")),
        "album": album.get("name") or "",
        "image_url": _first_image_url(album.get("images") or []),
        "external_url": (track.get("external_urls") or {}).get("spotify"),
    }


def _serialize_playback_item(item: dict) -> dict:
    if item.get("type") == "track":
        return {"type": "track", **_serialize_track(item)}

    show = item.get("show") or {}
    return {
        "type": item.get("type") or "item",
        "id": item.get("id"),
        "name": item.get("name") or "Untitled",
        "uri": item.get("uri"),
        "artist": show.get("publisher") or "",
        "album": show.get("name") or "",
        "image_url": _first_image_url(show.get("images") or item.get("images") or []),
        "external_url": (item.get("external_urls") or {}).get("spotify"),
    }


def _serialize_playlist(playlist: dict) -> dict:
    owner = playlist.get("owner") or {}
    tracks = playlist.get("tracks") or playlist.get("items") or {}
    return {
        "id": playlist.get("id"),
        "name": playlist.get("name") or "Untitled playlist",
        "uri": playlist.get("uri"),
        "owner": owner.get("display_name") or owner.get("id") or "",
        "tracks_total": tracks.get("total", 0),
        "image_url": _first_image_url(playlist.get("images") or []),
        "external_url": (playlist.get("external_urls") or {}).get("spotify"),
    }


def _first_image_url(images: list[dict]) -> str | None:
    for image in images:
        if image.get("url"):
            return image["url"]
    return None


def _encrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    return ENCRYPTED_TOKEN_PREFIX + _cipher().encrypt(token.encode("utf-8")).decode("utf-8")


def _decrypt_token(stored_token: str | None) -> str | None:
    if not stored_token:
        return None
    if not stored_token.startswith(ENCRYPTED_TOKEN_PREFIX):
        return stored_token

    encrypted = stored_token.removeprefix(ENCRYPTED_TOKEN_PREFIX).encode("utf-8")
    try:
        return _cipher().decrypt(encrypted).decode("utf-8")
    except InvalidToken:
        raise HTTPException(
            status_code=500,
            detail="Could not decrypt stored Spotify token. Check SPOTIFY_TOKEN_ENCRYPTION_KEY.",
        )


def _encrypt_legacy_tokens(user_id: int, row, access_token: str | None, refresh_token: str | None) -> None:
    access_is_legacy = row["access_token"] and not row["access_token"].startswith(ENCRYPTED_TOKEN_PREFIX)
    refresh_is_legacy = row["refresh_token"] and not row["refresh_token"].startswith(ENCRYPTED_TOKEN_PREFIX)
    if not access_is_legacy and not refresh_is_legacy:
        return
    db.execute(
        "UPDATE spotify_connections SET access_token = ?, refresh_token = ?, updated_at = ? WHERE user_id = ?",
        (_encrypt_token(access_token), _encrypt_token(refresh_token), auth.now_utc().isoformat(), user_id),
    )


def _cipher():
    global _token_cipher, _token_key_source
    key, source = _load_token_key()
    if _token_cipher is None or _token_key_source != source:
        if Fernet is None:
            raise HTTPException(
                status_code=500,
                detail="Spotify token encryption requires the cryptography package. Run pip install -r requirements.txt.",
            )
        try:
            _token_cipher = Fernet(key)
            _token_key_source = source
        except ValueError:
            raise HTTPException(
                status_code=500,
                detail="Invalid SPOTIFY_TOKEN_ENCRYPTION_KEY. Use a Fernet key.",
            )
    return _token_cipher


def _load_token_key() -> tuple[bytes, str]:
    env_key = os.getenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8"), "env:" + hashlib.sha256(env_key.encode("utf-8")).hexdigest()

    key_path = Path(os.getenv("SPOTIFY_TOKEN_KEY_FILE", TOKEN_KEY_FILE))
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
        return key.encode("utf-8"), str(key_path) + ":" + hashlib.sha256(key.encode("utf-8")).hexdigest()

    if Fernet is None:
        raise HTTPException(
            status_code=500,
            detail="Spotify token encryption requires the cryptography package. Run pip install -r requirements.txt.",
        )

    key = Fernet.generate_key()
    key_path.write_text(key.decode("utf-8"), encoding="utf-8")
    return key, str(key_path) + ":" + hashlib.sha256(key).hexdigest()


def _token_request(data: dict, settings: SpotifySettings) -> dict:
    try:
        response = requests.post(
            TOKEN_URL,
            data=data,
            auth=(settings.client_id, settings.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Spotify token request network error: %s", exc)
        raise ExternalServiceError("spotify", "Spotify token request failed") from exc

    if not response.ok:
        _raise_spotify_error(response, "Spotify token request failed")

    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError("spotify", "Spotify returned an invalid token response") from exc


def _spotify_request(method: str, path: str, access_token: str, **kwargs):
    try:
        response = requests.request(
            method,
            API_BASE_URL + path,
            headers={"Authorization": f"Bearer {access_token}", **kwargs.pop("headers", {})},
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        logger.warning("Spotify API network error %s %s: %s", method, path, exc)
        raise ExternalServiceError("spotify", "Spotify API request failed") from exc

    if response.status_code == 204:
        return None
    if not response.ok:
        _raise_spotify_error(response, "Spotify API request failed")
    if not response.content or not response.content.strip():
        return None
    try:
        return response.json()
    except ValueError:
        return None


_SAFE_CLIENT_MESSAGES = {
    400: "Spotify rejected the request.",
    401: "Spotify authorization expired. Reconnect Spotify.",
    403: "Spotify rejected this action. Spotify Premium and an active device may be required.",
    404: "Spotify resource not found.",
    429: "Too many Spotify requests. Please slow down and try again.",
}


def _raise_spotify_error(response: requests.Response, fallback: str) -> None:
    upstream_detail = ""
    try:
        body = response.json()
        error = body.get("error", body)
        if isinstance(error, dict):
            upstream_detail = error.get("message") or error.get("error_description") or ""
        elif isinstance(error, str):
            upstream_detail = body.get("error_description") or error
    except ValueError:
        upstream_detail = ""

    logger.warning(
        "Spotify upstream error status=%s detail=%s",
        response.status_code,
        upstream_detail or (response.text[:180] if response.text else ""),
    )

    client_message = _SAFE_CLIENT_MESSAGES.get(response.status_code, fallback)

    if 400 <= response.status_code < 500:
        raise HTTPException(status_code=response.status_code, detail=client_message)
    raise ExternalServiceError("spotify", client_message, status_code=502)
