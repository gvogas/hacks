from fastapi import HTTPException

from services import db, plant as plant_svc
from services.auth import now_utc

BASE_COIN_RATE_PER_MINUTE = 2
MAX_STUDY_TICK_SECONDS = 300

SHOP_UPGRADES = (
    {
        "id": "focus_engine",
        "name": "Focus Engine",
        "description": "Earn one extra coin per minute while studying for each level.",
        "base_cost": 40,
        "cost_step": 35,
        "max_level": 5,
        "effect_label": "+1 coin/min per level",
        "effect_type": "coin_rate",
    },
    {
        "id": "card_foundry",
        "name": "Card Foundry",
        "description": "Earn bonus coins when flashcards and quiz questions are generated.",
        "base_cost": 55,
        "cost_step": 45,
        "max_level": 4,
        "effect_label": "+4 learning coins per level",
        "effect_type": "learning_bonus",
        "bonus_coins": 4,
    },
    {
        "id": "quiz_magnet",
        "name": "Quiz Magnet",
        "description": "Earn bonus coins after submitting a quiz.",
        "base_cost": 70,
        "cost_step": 55,
        "max_level": 4,
        "effect_label": "+5 quiz coins per level",
        "effect_type": "quiz_bonus",
        "bonus_coins": 5,
    },
    {
        "id": "plan_compass",
        "name": "Plan Compass",
        "description": "Earn bonus coins when a personalized study plan is created.",
        "base_cost": 65,
        "cost_step": 50,
        "max_level": 3,
        "effect_label": "+6 plan coins per level",
        "effect_type": "plan_bonus",
        "bonus_coins": 6,
    },
)

SHOP_BY_ID = {item["id"]: item for item in SHOP_UPGRADES}


def ensure_progress(user_id: int) -> None:
    now = now_utc().isoformat()
    db.execute(
        "INSERT OR IGNORE INTO user_progress "
        "(user_id, coins, earned_coins, study_seconds, unpaid_seconds, created_at, updated_at) "
        "VALUES (?, 0, 0, 0, 0, ?, ?)",
        (user_id, now, now),
    )


def get_shop_state(user_id: int) -> dict:
    ensure_progress(user_id)
    progress = _progress_row(user_id)
    levels = _upgrade_levels(user_id)

    upgrades = [_serialize_upgrade(item, levels.get(item["id"], 0), progress["coins"]) for item in SHOP_UPGRADES]
    return {
        "coins": progress["coins"],
        "earned_coins": progress["earned_coins"],
        "study_seconds": progress["study_seconds"],
        "coin_rate_per_minute": coin_rate_per_minute(levels),
        "upgrades": upgrades,
        "plant": plant_svc.get_plant_state(user_id),
    }


def record_study_time(user_id: int, elapsed_seconds: int) -> dict:
    ensure_progress(user_id)
    seconds = max(0, min(int(elapsed_seconds), MAX_STUDY_TICK_SECONDS))
    progress = _progress_row(user_id)
    levels = _upgrade_levels(user_id)
    rate = coin_rate_per_minute(levels)

    total_unpaid_seconds = progress["unpaid_seconds"] + seconds
    payable_minutes = total_unpaid_seconds // 60
    coins_awarded = payable_minutes * rate
    remaining_seconds = total_unpaid_seconds % 60

    now = now_utc().isoformat()
    db.execute(
        "UPDATE user_progress SET "
        "coins = coins + ?, earned_coins = earned_coins + ?, "
        "study_seconds = study_seconds + ?, unpaid_seconds = ?, updated_at = ? "
        "WHERE user_id = ?",
        (coins_awarded, coins_awarded, seconds, remaining_seconds, now, user_id),
    )

    plant_svc.apply_study_tick(user_id, seconds)
    return {
        "coins_awarded": coins_awarded,
        "state": get_shop_state(user_id),
        "plant": plant_svc.get_plant_state(user_id),
    }


def purchase_upgrade(user_id: int, upgrade_id: str) -> dict:
    ensure_progress(user_id)
    item = SHOP_BY_ID.get(upgrade_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Upgrade not found")

    levels = _upgrade_levels(user_id)
    current_level = levels.get(upgrade_id, 0)
    if current_level >= item["max_level"]:
        raise HTTPException(status_code=400, detail="Upgrade is already maxed")

    cost = upgrade_cost(item, current_level)
    now = now_utc().isoformat()
    cur = db.execute(
        "UPDATE user_progress SET coins = coins - ?, updated_at = ? "
        "WHERE user_id = ? AND coins >= ?",
        (cost, now, user_id, cost),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=400, detail="Not enough coins")

    new_level = current_level + 1
    db.execute(
        "INSERT INTO user_upgrades (user_id, upgrade_id, level, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, upgrade_id) DO UPDATE SET "
        "level = excluded.level, updated_at = excluded.updated_at",
        (user_id, upgrade_id, new_level, now),
    )
    return {
        "upgrade_id": upgrade_id,
        "level": new_level,
        "spent": cost,
        "state": get_shop_state(user_id),
    }


def award_learning_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, "card_foundry")


def award_quiz_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, "quiz_magnet")


def award_plan_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, "plan_compass")


def deduct_coins(user_id: int, amount: int) -> int:
    """Deduct up to `amount` coins, never going below zero. Returns coins actually removed."""
    ensure_progress(user_id)
    amount = max(0, int(amount))
    if not amount:
        return 0
    progress = _progress_row(user_id)
    actual = min(amount, progress["coins"])
    if actual:
        now = now_utc().isoformat()
        db.execute(
            "UPDATE user_progress SET coins = coins - ?, updated_at = ? WHERE user_id = ?",
            (actual, now, user_id),
        )
    return actual


def grant_coins(user_id: int, amount: int) -> dict:
    ensure_progress(user_id)
    coins = max(0, int(amount))
    if coins:
        now = now_utc().isoformat()
        db.execute(
            "UPDATE user_progress SET coins = coins + ?, earned_coins = earned_coins + ?, updated_at = ? "
            "WHERE user_id = ?",
            (coins, coins, now, user_id),
        )
    return get_shop_state(user_id)


def coin_rate_per_minute(levels: dict[str, int]) -> int:
    return BASE_COIN_RATE_PER_MINUTE + levels.get("focus_engine", 0)


def upgrade_cost(item: dict, current_level: int) -> int:
    return item["base_cost"] + item["cost_step"] * current_level


def _award_upgrade_bonus(user_id: int, upgrade_id: str) -> int:
    item = SHOP_BY_ID[upgrade_id]
    levels = _upgrade_levels(user_id)
    amount = levels.get(upgrade_id, 0) * item["bonus_coins"]
    if amount:
        grant_coins(user_id, amount)
    return amount


def _progress_row(user_id: int):
    row = db.query_one("SELECT * FROM user_progress WHERE user_id = ?", (user_id,))
    if row is None:
        ensure_progress(user_id)
        row = db.query_one("SELECT * FROM user_progress WHERE user_id = ?", (user_id,))
    return row


def _upgrade_levels(user_id: int) -> dict[str, int]:
    rows = db.query_all(
        "SELECT upgrade_id, level FROM user_upgrades WHERE user_id = ?",
        (user_id,),
    )
    return {row["upgrade_id"]: row["level"] for row in rows}


def _serialize_upgrade(item: dict, level: int, coins: int) -> dict:
    maxed = level >= item["max_level"]
    next_cost = None if maxed else upgrade_cost(item, level)
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "effect_label": item["effect_label"],
        "level": level,
        "max_level": item["max_level"],
        "next_cost": next_cost,
        "affordable": bool(next_cost is not None and coins >= next_cost),
        "maxed": maxed,
    }
