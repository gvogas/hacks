from fastapi import APIRouter, HTTPException, Request

from agents.content_agent import ContentAgent
from agents.learning_agent import LearningAgent
from agents.research_agent import ResearchAgent
from models.schemas import GenerateLearningRequest, StudyStartRequest
from services import auth, session_store, shop
from services.exceptions import ExternalServiceError
from services.rate_limit import AI_LIMIT, limiter

router = APIRouter()
research_agent = ResearchAgent()
content_agent = ContentAgent()
learning_agent = LearningAgent()


@router.post("/start")
@limiter.limit(AI_LIMIT)
async def study_start(request: Request, req: StudyStartRequest, user: dict = auth.CurrentUser):
    session_id = session_store.ensure_session(req.session_id, user["id"])
    session = session_store.require_session(session_id, user["id"])

    if req.source != "files" and not req.topic:
        raise HTTPException(status_code=400, detail="Topic is required for web or combined search.")

    warnings: list[str] = []
    search_results: list[dict] = []

    if req.source in ("web", "both"):
        try:
            search_results = await research_agent.run(req.topic or "")
        except ExternalServiceError as exc:
            if req.source == "both" and session["uploaded_texts"]:
                warnings.append(str(exc))
                search_results = []
            else:
                raise HTTPException(status_code=503, detail="Web search failed. Please try again or choose files only.")

    uploaded_texts = session["uploaded_texts"] if req.source in ("files", "both") else []
    if req.source == "files" and not uploaded_texts:
        raise HTTPException(status_code=400, detail="No uploaded files found. Upload files first or choose web search.")

    notes = await content_agent.run(req.topic, search_results, uploaded_texts)
    session_store.update_session(session_id, user["id"], {"topic": req.topic or session.get("topic", ""), "notes": notes})
    return {"session_id": session_id, "notes": notes, "warnings": warnings}


@router.post("/generate-learning")
@limiter.limit(AI_LIMIT)
async def generate_learning(request: Request, req: GenerateLearningRequest, user: dict = auth.CurrentUser):
    session = session_store.require_session(req.session_id, user["id"])
    if not session["notes"]:
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    result = await learning_agent.run(
        session["notes"],
        num_flashcards=req.num_flashcards,
        num_questions=req.num_questions,
        difficulty=req.difficulty,
    )
    session_store.update_session(req.session_id, user["id"], {
        "flashcards": result.get("flashcards", []),
        "quiz_questions": result.get("quiz_questions", []),
    })
    coins_awarded = shop.award_learning_bonus(user["id"])
    return {"session_id": req.session_id, "coins_awarded": coins_awarded, **result}


@router.get("/sessions")
async def list_user_sessions(user: dict = auth.CurrentUser):
    return {"sessions": session_store.list_sessions(user["id"])}


@router.get("/session/{session_id}")
async def get_session(session_id: str, user: dict = auth.CurrentUser):
    session = session_store.require_session(session_id, user["id"])
    return {"session_id": session_id, **session}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user: dict = auth.CurrentUser):
    if not session_store.delete_session(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": session_id}
