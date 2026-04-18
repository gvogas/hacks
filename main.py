from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from routers import study, upload, quiz, plan, auth as auth_router
from services import db as _db
from services.exceptions import ExternalServiceError

# Eagerly open the DB so schema migrations run at startup, not on first request.
_db.get_conn()

app = FastAPI(title="AI Student Agent")


@app.exception_handler(ExternalServiceError)
async def _external_service_error(_: Request, exc: ExternalServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(study.router, prefix="/api/study", tags=["study"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
app.include_router(plan.router, prefix="/api/plan", tags=["plan"])

@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
