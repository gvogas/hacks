import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from services import auth, db, plant as plant_svc, shop

router = APIRouter()


class ClaimLevelRequest(BaseModel):
    level_id: str


@router.get("/")
async def get_profile(user: dict = auth.CurrentUser):
    shop.ensure_progress(user["id"])
    progress = db.query_one(
        "SELECT coins, earned_coins, study_seconds FROM user_progress WHERE user_id = ?",
        (user["id"],),
    )

    session_rows = db.query_all(
        "SELECT id, topic, data, updated_at FROM sessions WHERE user_id = ? "
        "ORDER BY updated_at DESC",
        (user["id"],),
    )

    quiz_attempts: list[dict] = []
    total_quizzes = 0
    total_percentage = 0.0
    for row in session_rows:
        try:
            data = json.loads(row["data"] or "{}")
        except Exception:
            continue
        for entry in data.get("quiz_history", []) or []:
            total_quizzes += 1
            total_percentage += float(entry.get("percentage") or 0)
            quiz_attempts.append({
                "session_id": row["id"],
                "topic": row["topic"] or "Untitled",
                "timestamp": entry.get("timestamp"),
                "score": entry.get("score"),
                "total": entry.get("total"),
                "percentage": entry.get("percentage"),
                "weak_topics": entry.get("weak_topics", []),
            })

    quiz_attempts.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    avg_percentage = round(total_percentage / total_quizzes, 1) if total_quizzes else 0

    return {
        "stats": {
            "study_seconds": progress["study_seconds"] if progress else 0,
            "coins": progress["coins"] if progress else 0,
            "earned_coins": progress["earned_coins"] if progress else 0,
            "total_quizzes": total_quizzes,
            "avg_percentage": avg_percentage,
            "total_sessions": len(session_rows),
        },
        "quiz_history": quiz_attempts[:15],
        "plant": plant_svc.get_plant_state(user["id"]),
        "levels": plant_svc.get_levels_state(user["id"]),
    }


@router.post("/claim")
async def claim_level(req: ClaimLevelRequest, user: dict = auth.CurrentUser):
    result = plant_svc.claim_level(user["id"], req.level_id)
    result["plant"] = plant_svc.get_plant_state(user["id"])
    result["levels"] = plant_svc.get_levels_state(user["id"])
    result["shop"] = shop.get_shop_state(user["id"])
    return result


@router.post("/admin-unlock")
async def admin_unlock(user: dict = auth.CurrentUser):
    now = auth.now_utc().isoformat()
    claimed = plant_svc._claimed_level_ids(user["id"])
    for lvl in plant_svc.PLANT_LEVELS:
        if lvl["id"] not in claimed:
            db.execute(
                "INSERT INTO user_plant_rewards (user_id, level_id, claimed_at) VALUES (?, ?, ?)",
                (user["id"], lvl["id"], now),
            )
    db.execute(
        "UPDATE user_progress SET coins = 9999, plant_xp = 9999, plant_health = 100, updated_at = ? WHERE user_id = ?",
        (now, user["id"]),
    )
    return {
        "plant": plant_svc.get_plant_state(user["id"]),
        "levels": plant_svc.get_levels_state(user["id"]),
        "shop": shop.get_shop_state(user["id"]),
    }
