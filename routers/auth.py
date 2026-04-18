from fastapi import APIRouter

from models.schemas import LoginRequest, SignupRequest
from services import auth

router = APIRouter()


@router.post("/signup")
async def signup(req: SignupRequest):
    return auth.issue_session(auth.create_user(req.email, req.password))


@router.post("/login")
async def login(req: LoginRequest):
    return auth.issue_session(auth.authenticate(req.email, req.password))


@router.get("/me")
async def me(user: dict = auth.CurrentUser):
    return {"user": user}
