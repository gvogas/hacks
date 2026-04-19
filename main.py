import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

load_dotenv()

from routers import study, upload, quiz, plan, shop, profile, spotify, plant, auth as auth_router
from services import db as _db
from services.exceptions import ExternalServiceError
from services.rate_limit import limiter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / os.getenv("FRONTEND_DIR", "frontend")
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return values or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s; using %s", name, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y", "t"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Open the DB during app startup so schema creation fails fast.
    _db.get_conn()
    logger.info("Database initialized at %s", _db.DB_PATH)
    try:
        yield
    finally:
        _db.close_conn()


def create_app() -> FastAPI:
    app = FastAPI(title=os.getenv("APP_NAME", "AI Student Agent"), lifespan=lifespan)

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_env_csv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
        allow_methods=_env_csv(
            "CORS_METHODS",
            ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        ),
        allow_headers=_env_csv(
            "CORS_HEADERS",
            ["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        ),
        allow_credentials=_env_bool("CORS_ALLOW_CREDENTIALS", False),
        max_age=600,
    )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(ExternalServiceError, _external_service_error)
    app.add_exception_handler(sqlite3.Error, _database_error)

    app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
    app.include_router(study.router, prefix="/api/study", tags=["study"])
    app.include_router(upload.router, prefix="/api", tags=["upload"])
    app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
    app.include_router(plan.router, prefix="/api/plan", tags=["plan"])
    app.include_router(shop.router, prefix="/api/shop", tags=["shop"])
    app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
    app.include_router(spotify.router, prefix="/api/spotify", tags=["spotify"])
    app.include_router(plant.router, prefix="/api/plant", tags=["plant"])

    @app.get("/api/health", tags=["system"])
    async def health():
        _db.query_one("SELECT 1")
        return {"status": "ok", "database": "ok"}

    sprites_dir = BASE_DIR / "Sprites"
    if sprites_dir.exists():
        app.mount("/sprites", StaticFiles(directory=sprites_dir), name="sprites")

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    else:
        logger.warning("Frontend directory not found: %s", FRONTEND_DIR)

        @app.get("/", tags=["system"])
        async def frontend_missing():
            return {"detail": f"Frontend directory not found: {FRONTEND_DIR}"}

    return app


async def _external_service_error(_: Request, exc: ExternalServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc), "service": exc.service},
    )


async def _database_error(_: Request, exc: sqlite3.Error):
    logger.error("Database error", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": "Database error"})


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=_env_int("PORT", 8000),
        reload=_env_bool("RELOAD", True),
    )
