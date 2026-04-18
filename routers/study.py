from fastapi import APIRouter, HTTPException
from models.schemas import StudyStartRequest, GenerateLearningRequest
from agents.research_agent import ResearchAgent
from agents.content_agent import ContentAgent
from agents.learning_agent import LearningAgent
from services import session_store

router = APIRouter()
research_agent = ResearchAgent()
content_agent = ContentAgent()
learning_agent = LearningAgent()


@router.post("/start")
async def study_start(req: StudyStartRequest):
    session_id = session_store.ensure_session(req.session_id)

    search_results = await research_agent.run(req.topic)
    session = session_store.get_session(session_id)
    uploaded_texts = session.get("uploaded_texts", [])

    notes = await content_agent.run(req.topic, search_results, uploaded_texts)

    session_store.update_session(session_id, {"topic": req.topic, "notes": notes})
    return {"session_id": session_id, "notes": notes}


@router.post("/generate-learning")
async def generate_learning(req: GenerateLearningRequest):
    session = session_store.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("notes"):
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    result = await learning_agent.run(
        session["notes"],
        num_flashcards=req.num_flashcards,
        num_questions=req.num_questions,
    )

    session_store.update_session(req.session_id, {
        "flashcards": result.get("flashcards", []),
        "quiz_questions": result.get("quiz_questions", []),
    })
    return {"session_id": req.session_id, **result}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, **session}
