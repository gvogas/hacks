from fastapi import APIRouter, Request

from models.schemas import LoginRequest, SignupRequest
from services import auth
from services.rate_limit import AUTH_LIMIT, limiter

router = APIRouter()


@router.post("/signup")
@limiter.limit(AUTH_LIMIT)
async def signup(request: Request, req: SignupRequest):
    return auth.issue_session(auth.create_user(req.email, req.password))


@router.post("/login")
@limiter.limit(AUTH_LIMIT)
async def login(request: Request, req: LoginRequest):
    return auth.issue_session(auth.authenticate(req.email, req.password))


@router.get("/me")
async def me(user: dict = auth.CurrentUser):
    return {"user": user}
