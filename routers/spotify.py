import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from models.schemas import SpotifyPlayRequest, SpotifyTransferRequest
from services import auth, spotify
from services.exceptions import ExternalServiceError
from services.rate_limit import SPOTIFY_LIMIT, limiter

router = APIRouter()
logger = logging.getLogger(__name__)
COOKIE_NAME = "spotify_oauth_nonce"
_GENERIC_CALLBACK_ERROR = "Spotify connection failed. Please try again."


@router.get("/status")
async def status(user: dict = auth.CurrentUser):
    return spotify.get_status(user["id"])


@router.post("/connect")
@limiter.limit(SPOTIFY_LIMIT)
async def connect(request: Request, user: dict = auth.CurrentUser):
    authorization = spotify.build_authorization(user["id"])
    response = JSONResponse({"auth_url": authorization["auth_url"]})
    response.set_cookie(
        COOKIE_NAME,
        authorization["nonce"],
        max_age=spotify.STATE_TTL_MINUTES * 60,
        path="/api/spotify",
        secure=_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback", include_in_schema=False)
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    redirect_to = _spotify_return_url("connected")
    if error:
        redirect_to = _spotify_return_url("denied", "Spotify authorization was cancelled or denied.")
    else:
        try:
            spotify.complete_authorization(code, state, request.cookies.get(COOKIE_NAME))
        except (HTTPException, ExternalServiceError):
            logger.warning("Spotify OAuth callback failed", exc_info=True)
            redirect_to = _spotify_return_url("error", _GENERIC_CALLBACK_ERROR)
        except Exception:
            logger.exception("Unexpected Spotify OAuth callback failure")
            redirect_to = _spotify_return_url("error", _GENERIC_CALLBACK_ERROR)

    response = RedirectResponse(redirect_to, status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/api/spotify")
    return response


@router.post("/disconnect")
async def disconnect(user: dict = auth.CurrentUser):
    return spotify.disconnect(user["id"])


@router.get("/token")
async def web_playback_token(user: dict = auth.CurrentUser):
    access_token = spotify.valid_access_token(user["id"])
    return {"access_token": access_token}


@router.get("/devices")
async def devices(user: dict = auth.CurrentUser):
    return spotify.get_available_devices(user["id"])


@router.get("/search")
@limiter.limit(SPOTIFY_LIMIT)
async def search(
    request: Request,
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=8, ge=1, le=20),
    user: dict = auth.CurrentUser,
):
    return spotify.search_catalog(user["id"], q, limit=limit)


@router.get("/playlists")
@limiter.limit(SPOTIFY_LIMIT)
async def playlists(request: Request, limit: int = Query(default=20, ge=1, le=50), user: dict = auth.CurrentUser):
    return spotify.get_user_playlists(user["id"], limit=limit)


@router.get("/current")
@limiter.limit(SPOTIFY_LIMIT)
async def current(request: Request, user: dict = auth.CurrentUser):
    return spotify.get_current_playback(user["id"])


@router.put("/transfer")
@limiter.limit(SPOTIFY_LIMIT)
async def transfer(request: Request, req: SpotifyTransferRequest, user: dict = auth.CurrentUser):
    return spotify.transfer_playback(user["id"], req.device_id, play=req.play)


@router.put("/play")
@limiter.limit(SPOTIFY_LIMIT)
async def play(request: Request, req: SpotifyPlayRequest | None = Body(default=None), user: dict = auth.CurrentUser):
    return spotify.start_or_resume_playback(
        user["id"],
        context_uri=req.context_uri if req else None,
        uris=req.uris if req else None,
        device_id=req.device_id if req else None,
    )


@router.put("/pause")
@limiter.limit(SPOTIFY_LIMIT)
async def pause(request: Request, user: dict = auth.CurrentUser):
    return spotify.pause_playback(user["id"])


@router.post("/next")
@limiter.limit(SPOTIFY_LIMIT)
async def next_track(request: Request, user: dict = auth.CurrentUser):
    return spotify.next_track(user["id"])


@router.post("/previous")
@limiter.limit(SPOTIFY_LIMIT)
async def previous_track(request: Request, user: dict = auth.CurrentUser):
    return spotify.previous_track(user["id"])


def _cookie_secure(request: Request) -> bool:
    raw = os.getenv("SPOTIFY_COOKIE_SECURE", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    scheme = forwarded_proto or request.url.scheme
    return scheme == "https"


def _spotify_return_url(result: str, detail: str | None = None) -> str:
    params = {"spotify": result}
    if detail:
        params["spotify_detail"] = detail[:240]
    return "/?" + urlencode(params)
