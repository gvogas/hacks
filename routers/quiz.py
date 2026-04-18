from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import QuizSubmitRequest
from services import auth, session_store, shop, plant as plant_svc

router = APIRouter()


@router.post("/submit")
async def submit_quiz(req: QuizSubmitRequest, user: dict = auth.CurrentUser):
    session = session_store.require_session(req.session_id, user["id"])

    questions = session.get("quiz_questions", [])
    if not questions:
        raise HTTPException(status_code=400, detail="No quiz questions found.")

    submitted = {ans.question_id: ans.selected.strip().upper() for ans in req.answers}
    results = []
    wrong_ids = []
    weak_topic_counts: dict[str, int] = {}
    score = 0

    for index, q in enumerate(questions):
        question_id = q.get("id", index)
        selected = submitted.get(question_id, "")
        correct_answer = str(q.get("answer", "")).strip().upper()
        correct = bool(selected) and selected == correct_answer
        if correct:
            score += 1
        results.append({
            "question_id": question_id,
            "question": q.get("question", ""),
            "selected": selected,
            "correct_answer": correct_answer,
            "is_correct": correct,
            "explanation": q.get("explanation", ""),
        })
        if not correct:
            wrong_ids.append(question_id)
            tag = q.get("topic_tag", "General")
            weak_topic_counts[tag] = weak_topic_counts.get(tag, 0) + 1

    weak_topics = [t for t, count in weak_topic_counts.items() if count >= 1]
    total = len(questions)

    history_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "total": total,
        "percentage": round(score / total * 100, 1) if total else 0,
        "wrong_question_ids": wrong_ids,
        "weak_topics": weak_topics,
    }

    existing_history = session.get("quiz_history", [])
    existing_history.append(history_entry)
    session_store.update_session(req.session_id, user["id"], {"quiz_history": existing_history})
    coins_awarded = shop.award_quiz_bonus(user["id"])
    if score > 0:
        plant_svc.apply_heal(user["id"], score * plant_svc.HEAL_PER_CORRECT)
    plant_state = plant_svc.apply_wrong_answers(user["id"], len(wrong_ids))

    death_penalty = 0
    if plant_state.get("just_died"):
        death_penalty = shop.deduct_coins(user["id"], 30)

    return {
        "session_id": req.session_id,
        "score": score,
        "total": total,
        "percentage": history_entry["percentage"],
        "weak_topics": weak_topics,
        "results": results,
        "coins_awarded": coins_awarded,
        "wrong_count": len(wrong_ids),
        "plant": plant_state,
        "death_penalty": death_penalty,
    }
