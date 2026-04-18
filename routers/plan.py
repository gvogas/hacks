from fastapi import APIRouter, HTTPException

from agents.planning_agent import PlanningAgent
from models.schemas import PlanGenerateRequest
from services import auth, session_store, shop

router = APIRouter()
planning_agent = PlanningAgent()


@router.post("/generate")
async def generate_plan(req: PlanGenerateRequest, user: dict = auth.CurrentUser):
    session = session_store.require_session(req.session_id, user["id"])
    if not session["notes"]:
        raise HTTPException(status_code=400, detail="No notes found. Run /study/start first.")

    history = session["quiz_history"]
    weak_topics = history[-1]["weak_topics"] if history else []

    plan = await planning_agent.run(
        notes=session["notes"],
        weak_topics=weak_topics,
        available_days=req.available_days,
        hours_per_day=req.hours_per_day,
    )
    session_store.update_session(req.session_id, user["id"], {"study_plan": plan})
    coins_awarded = shop.award_plan_bonus(user["id"])
    return {"session_id": req.session_id, "coins_awarded": coins_awarded, **plan}
