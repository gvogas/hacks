from fastapi import APIRouter, HTTPException
from datetime import datetime
from models.schemas import QuizSubmitRequest
from services import session_store

router = APIRouter()


@router.post("/submit")
async def submit_quiz(req: QuizSubmitRequest):
    session = session_store.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    questions = session.get("quiz_questions", [])
    if not questions:
        raise HTTPException(status_code=400, detail="No quiz questions found.")

    q_map = {q["id"]: q for q in questions}
    results = []
    wrong_ids = []
    weak_topic_counts: dict[str, int] = {}

    for ans in req.answers:
        q = q_map.get(ans.question_id)
        if not q:
            continue
        correct = ans.selected.upper() == q["answer"].upper()
        results.append({
            "question_id": ans.question_id,
            "question": q["question"],
            "selected": ans.selected,
            "correct_answer": q["answer"],
            "is_correct": correct,
            "explanation": q.get("explanation", ""),
        })
        if not correct:
            wrong_ids.append(ans.question_id)
            tag = q.get("topic_tag", "General")
            weak_topic_counts[tag] = weak_topic_counts.get(tag, 0) + 1

    weak_topics = [t for t, count in weak_topic_counts.items() if count >= 1]
    score = len(req.answers) - len(wrong_ids)
    total = len(req.answers)

    history_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "score": score,
        "total": total,
        "percentage": round(score / total * 100, 1) if total else 0,
        "wrong_question_ids": wrong_ids,
        "weak_topics": weak_topics,
    }

    existing_history = session.get("quiz_history", [])
    existing_history.append(history_entry)
    session_store.update_session(req.session_id, {"quiz_history": existing_history})

    return {
        "session_id": req.session_id,
        "score": score,
        "total": total,
        "percentage": history_entry["percentage"],
        "weak_topics": weak_topics,
        "results": results,
    }
