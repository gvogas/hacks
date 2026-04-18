from fastapi import HTTPException

from services import db
from services.auth import now_utc

WITHER_PER_WRONG = 20
HEALTH_PER_MINUTE = 3
HEAL_PER_CORRECT = 5
HEAL_PER_FLASHCARD = 2
XP_PER_SECOND = 0.1  # 1 XP per 10 seconds

STAGE_THRESHOLDS = [0, 60, 180, 360, 600, 900]
STAGE_NAMES = ["Seed", "Sprout", "Seedling", "Young Plant", "Budding", "Full Bloom"]

PLANT_LEVELS = [
    {
        "id": "bad", "name": "Bad", "min_xp": 0, "coin_reward": 5, "skin": "default",
        "description": "A tiny seed full of hope. Every great plant starts here — "
                       "don't be discouraged by humble beginnings.",
    },
    {
        "id": "average", "name": "Average", "min_xp": 120, "coin_reward": 25, "skin": "warm",
        "description": "Your plant is showing signs of life. A steady study habit "
                       "is starting to take root.",
    },
    {
        "id": "good", "name": "Good", "min_xp": 300, "coin_reward": 75, "skin": "lush",
        "description": "A healthy, growing plant with vibrant foliage. Your "
                       "consistency is paying off.",
    },
    {
        "id": "excellent", "name": "Excellent", "min_xp": 600, "coin_reward": 150, "skin": "azure",
        "description": "An excellent specimen with strong roots and deep green "
                       "leaves. Rare dedication on display here.",
    },
    {
        "id": "amazing", "name": "Amazing", "min_xp": 1000, "coin_reward": 300, "skin": "sunset",
        "description": "An amazing plant bathed in warm hues. Few students "
                       "ever see their plant reach this point.",
    },
    {
        "id": "phenomenal", "name": "Phenomenal", "min_xp": 1500, "coin_reward": 600, "skin": "aurora",
        "description": "Phenomenal! Your plant glows with aurora-like energy — "
                       "a beacon of study discipline.",
    },
    {
        "id": "legendary", "name": "Legendary", "min_xp": 2500, "coin_reward": 1500, "skin": "golden",
        "description": "Legendary. A golden bloom whispered about in study halls. "
                       "You have mastered the art of consistency.",
    },
]

LEVELS_BY_ID = {lvl["id"]: lvl for lvl in PLANT_LEVELS}


def get_plant_state(user_id: int) -> dict:
    row = db.query_one(
        "SELECT COALESCE(plant_xp, 0) AS plant_xp, "
        "COALESCE(plant_health, 100) AS plant_health, "
        "COALESCE(plant_skin, 'default') AS plant_skin "
        "FROM user_progress WHERE user_id = ?",
        (user_id,),
    )
    if row is None:
        return _build_state(0, 100, "default")
    return _build_state(row["plant_xp"], row["plant_health"], row["plant_skin"])


def _claimed_level_ids(user_id: int) -> set[str]:
    rows = db.query_all(
        "SELECT level_id FROM user_plant_rewards WHERE user_id = ?",
        (user_id,),
    )
    return {r["level_id"] for r in rows}


def get_levels_state(user_id: int) -> list[dict]:
    state = get_plant_state(user_id)
    xp = state["xp"]
    claimed = _claimed_level_ids(user_id)
    result = []
    for lvl in PLANT_LEVELS:
        reached = xp >= lvl["min_xp"]
        is_claimed = lvl["id"] in claimed
        result.append({
            "id": lvl["id"],
            "name": lvl["name"],
            "min_xp": lvl["min_xp"],
            "coin_reward": lvl["coin_reward"],
            "skin": lvl["skin"],
            "description": lvl["description"],
            "reached": reached,
            "claimed": is_claimed,
            "equipped": state["skin"] == lvl["skin"],
        })
    return result


def claim_level(user_id: int, level_id: str) -> dict:
    lvl = LEVELS_BY_ID.get(level_id)
    if lvl is None:
        raise HTTPException(status_code=404, detail="Unknown level")

    state = get_plant_state(user_id)
    if state["xp"] < lvl["min_xp"]:
        raise HTTPException(status_code=400, detail="Plant has not reached this level yet")

    claimed = _claimed_level_ids(user_id)
    already_claimed = level_id in claimed
    now = now_utc().isoformat()

    coins_awarded = 0
    if not already_claimed:
        db.execute(
            "INSERT INTO user_plant_rewards (user_id, level_id, claimed_at) VALUES (?, ?, ?)",
            (user_id, level_id, now),
        )
        coins_awarded = lvl["coin_reward"]
        db.execute(
            "UPDATE user_progress SET coins = coins + ?, earned_coins = earned_coins + ?, "
            "updated_at = ? WHERE user_id = ?",
            (coins_awarded, coins_awarded, now, user_id),
        )

    # Equip the skin regardless (re-equip allowed for already-claimed levels)
    db.execute(
        "UPDATE user_progress SET plant_skin = ?, updated_at = ? WHERE user_id = ?",
        (lvl["skin"], now, user_id),
    )

    return {
        "level_id": level_id,
        "coins_awarded": coins_awarded,
        "skin": lvl["skin"],
        "already_claimed": already_claimed,
    }


def apply_study_tick(user_id: int, seconds: int) -> None:
    xp_gain = int(seconds * XP_PER_SECOND)
    health_gain = int((seconds / 60.0) * HEALTH_PER_MINUTE)
    now = now_utc().isoformat()
    db.execute(
        "UPDATE user_progress SET "
        "plant_xp = COALESCE(plant_xp, 0) + ?, "
        "plant_health = MIN(100, COALESCE(plant_health, 100) + ?), "
        "updated_at = ? WHERE user_id = ?",
        (xp_gain, health_gain, now, user_id),
    )


def apply_heal(user_id: int, amount: int) -> dict:
    if amount <= 0:
        return get_plant_state(user_id)
    now = now_utc().isoformat()
    db.execute(
        "UPDATE user_progress SET "
        "plant_health = MIN(100, COALESCE(plant_health, 100) + ?), "
        "updated_at = ? WHERE user_id = ?",
        (amount, now, user_id),
    )
    return get_plant_state(user_id)


def apply_wrong_answers(user_id: int, wrong_count: int) -> dict:
    state = get_plant_state(user_id)
    if wrong_count <= 0:
        state["just_died"] = False
        return state
    prev_health = state["health"]
    damage = wrong_count * WITHER_PER_WRONG
    now = now_utc().isoformat()
    db.execute(
        "UPDATE user_progress SET "
        "plant_health = MAX(0, COALESCE(plant_health, 100) - ?), "
        "updated_at = ? WHERE user_id = ?",
        (damage, now, user_id),
    )
    new_state = get_plant_state(user_id)
    new_state["just_died"] = prev_health > 0 and new_state["health"] <= 0
    return new_state


def _build_state(xp: int, health: int, skin: str = "default") -> dict:
    stage = 0
    for i, threshold in enumerate(STAGE_THRESHOLDS):
        if xp >= threshold:
            stage = i
    next_xp = STAGE_THRESHOLDS[stage + 1] if stage < len(STAGE_THRESHOLDS) - 1 else None
    stage_xp_start = STAGE_THRESHOLDS[stage]
    if next_xp is not None:
        stage_range = next_xp - stage_xp_start
        stage_progress = min(100, int(((xp - stage_xp_start) / stage_range) * 100))
    else:
        stage_progress = 100

    # Current level tier (highest reached)
    current_level = PLANT_LEVELS[0]
    for lvl in PLANT_LEVELS:
        if xp >= lvl["min_xp"]:
            current_level = lvl
    return {
        "xp": xp,
        "health": health,
        "skin": skin,
        "stage": stage,
        "stage_name": STAGE_NAMES[stage],
        "next_stage_xp": next_xp,
        "stage_progress": stage_progress,
        "level_id": current_level["id"],
        "level_name": current_level["name"],
    }
