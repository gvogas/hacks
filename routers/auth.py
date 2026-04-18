from fastapi import APIRouter

from models.schemas import LoginRequest, SignupRequest
from services import auth

router = APIRouter()


@router.post("/signup")
async def signup(req: SignupRequest):
    user = auth.create_user(req.email, req.password)
    token = auth.make_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.post("/login")
async def login(req: LoginRequest):
    user = auth.authenticate(req.email, req.password)
    token = auth.make_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.get("/me")
async def me(user: dict = auth.CurrentUser):
    return {"user": user}
