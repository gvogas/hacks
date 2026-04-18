from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from routers import study, upload, quiz, plan

app = FastAPI(title="AI Student Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(study.router, prefix="/api/study", tags=["study"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
app.include_router(plan.router, prefix="/api/plan", tags=["plan"])

@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
