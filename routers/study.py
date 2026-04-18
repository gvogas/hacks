from fastapi import APIRouter, HTTPException

from agents.content_agent import ContentAgent
from agents.learning_agent import LearningAgent
from agents.research_agent import ResearchAgent
from models.schemas import GenerateLearningRequest, StudyStartRequest
from services import auth, session_store, shop
from services.exceptions import ExternalServiceError

router = APIRouter()
research_agent = ResearchAgent()
content_agent = ContentAgent()
learning_agent = LearningAgent()


@router.post("/start")
async def study_start(req: StudyStartRequest, user: dict = auth.CurrentUser):
    session_id = session_store.ensure_session(req.session_id, user["id"])

    warnings: list[str] = []
    try:
        search_results = await research_agent.run(req.topic)
    except ExternalServiceError as exc:
        # Web search is best-effort; fall back to uploaded notes alone.
        search_results = []
        warnings.append(str(exc))

    session = session_store.require_session(session_id, user["id"])
    notes = await content_agent.run(req.topic, search_results, session["uploaded_texts"])

    session_store.update_session(session_id, user["id"], {"topic": req.topic, "notes": notes})
    return {"session_id": session_id, "notes": notes, "warnings": warnings}


@router.post("/generate-learning")
async def generate_learning(req: GenerateLearningRequest, user: dict = auth.CurrentUser):
    session = session_store.require_session(req.session_id, user["id"])
    if not session["notes"]:
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    result = await learning_agent.run(
        session["notes"],
        num_flashcards=req.num_flashcards,
        num_questions=req.num_questions,
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
