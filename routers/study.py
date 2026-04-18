from fastapi import APIRouter, HTTPException
from models.schemas import StudyStartRequest, GenerateLearningRequest
from agents.research_agent import ResearchAgent
from agents.content_agent import ContentAgent
from agents.learning_agent import LearningAgent
from services import session_store, auth
from services.exceptions import ExternalServiceError

router = APIRouter()
research_agent = ResearchAgent()
content_agent = ContentAgent()
learning_agent = LearningAgent()


@router.post("/start")
async def study_start(req: StudyStartRequest, user: dict = auth.CurrentUser):
    session_id = session_store.ensure_session(req.session_id, user["id"])

    warnings = []
    try:
        search_results = await research_agent.run(req.topic)
    except ExternalServiceError as exc:
        search_results = []
        warnings.append(str(exc))

    session = session_store.require_session(session_id, user["id"])
    uploaded_texts = session.get("uploaded_texts", [])

    try:
        notes = await content_agent.run(req.topic, search_results, uploaded_texts)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    session_store.update_session(session_id, user["id"], {"topic": req.topic, "notes": notes})
    return {"session_id": session_id, "notes": notes, "warnings": warnings}


@router.post("/generate-learning")
async def generate_learning(req: GenerateLearningRequest, user: dict = auth.CurrentUser):
    session = session_store.require_session(req.session_id, user["id"])
    if not session.get("notes"):
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    try:
        result = await learning_agent.run(
            session["notes"],
            num_flashcards=req.num_flashcards,
            num_questions=req.num_questions,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    session_store.update_session(req.session_id, user["id"], {
        "flashcards": result.get("flashcards", []),
        "quiz_questions": result.get("quiz_questions", []),
    })
    return {"session_id": req.session_id, **result}


@router.get("/sessions")
async def list_user_sessions(user: dict = auth.CurrentUser):
    return {"sessions": session_store.list_sessions(user["id"])}


@router.get("/session/{session_id}")
async def get_session(session_id: str, user: dict = auth.CurrentUser):
    session = session_store.require_session(session_id, user["id"])
    return {"session_id": session_id, **session}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user: dict = auth.CurrentUser):
    deleted = session_store.delete_session(session_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": session_id}
