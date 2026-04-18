from fastapi import APIRouter, HTTPException
from models.schemas import PlanGenerateRequest
from agents.planning_agent import PlanningAgent
from services import session_store

router = APIRouter()
planning_agent = PlanningAgent()


@router.post("/generate")
async def generate_plan(req: PlanGenerateRequest):
    session = session_store.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("notes"):
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    latest_history = session.get("quiz_history", [])
    weak_topics: list[str] = []
    if latest_history:
        weak_topics = latest_history[-1].get("weak_topics", [])

    plan = await planning_agent.run(
        notes=session["notes"],
        weak_topics=weak_topics,
        available_days=req.available_days,
        hours_per_day=req.hours_per_day,
    )

    session_store.update_session(req.session_id, {"study_plan": plan})
    return {"session_id": req.session_id, **plan}
