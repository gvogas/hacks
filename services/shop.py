from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException

from services import db, plant as plant_svc
from services.auth import now_utc

BASE_COIN_RATE_PER_MINUTE = 2
MAX_STUDY_TICK_SECONDS = 300

FOCUS_ENGINE = "focus_engine"
CARD_FOUNDRY = "card_foundry"
QUIZ_MAGNET = "quiz_magnet"
PLAN_COMPASS = "plan_compass"

UpgradeKind = Literal["coin_rate", "learning_bonus", "quiz_bonus", "plan_bonus"]


@dataclass(frozen=True, slots=True)
class Upgrade:
    id: str
    name: str
    description: str
    base_cost: int
    cost_step: int
    max_level: int
    effect_label: str
    kind: UpgradeKind
    bonus_coins: int = 0

    def next_cost(self, level: int) -> int | None:
        if level >= self.max_level:
            return None
        return self.base_cost + self.cost_step * level


SHOP_UPGRADES: tuple[Upgrade, ...] = (
    Upgrade(
        id=FOCUS_ENGINE,
        name="Focus Engine",
        description="Earn one extra coin per minute while studying for each level.",
        base_cost=40,
        cost_step=35,
        max_level=5,
        effect_label="+1 coin/min per level",
        kind="coin_rate",
    ),
    Upgrade(
        id=CARD_FOUNDRY,
        name="Card Foundry",
        description="Earn bonus coins when flashcards and quiz questions are generated.",
        base_cost=55,
        cost_step=45,
        max_level=4,
        effect_label="+4 learning coins per level",
        kind="learning_bonus",
        bonus_coins=4,
    ),
    Upgrade(
        id=QUIZ_MAGNET,
        name="Quiz Magnet",
        description="Earn bonus coins after submitting a quiz.",
        base_cost=70,
        cost_step=55,
        max_level=4,
        effect_label="+5 quiz coins per level",
        kind="quiz_bonus",
        bonus_coins=5,
    ),
    Upgrade(
        id=PLAN_COMPASS,
        name="Plan Compass",
        description="Earn bonus coins when a personalized study plan is created.",
        base_cost=65,
        cost_step=50,
        max_level=3,
        effect_label="+6 plan coins per level",
        kind="plan_bonus",
        bonus_coins=6,
    ),
)

SHOP_BY_ID = {upgrade.id: upgrade for upgrade in SHOP_UPGRADES}


def ensure_progress(user_id: int) -> None:
    with db.transaction() as conn:
        _ensure_progress(conn, user_id)


def get_shop_state(user_id: int) -> dict:
    ensure_progress(user_id)
    progress = _progress_row(user_id)
    levels = _upgrade_levels(user_id)
    coins = progress["coins"]

    return {
        "coins": coins,
        "earned_coins": progress["earned_coins"],
        "study_seconds": progress["study_seconds"],
        "seconds_until_next_coin": (60 - progress["unpaid_seconds"]) % 60,
        "coin_rate_per_minute": coin_rate_per_minute(levels),
        "upgrades": [_serialize_upgrade(upgrade, levels.get(upgrade.id, 0), coins) for upgrade in SHOP_UPGRADES],
        "plant": plant_svc.get_plant_state(user_id),
    }


def record_study_time(user_id: int, elapsed_seconds: int) -> dict:
    seconds = min(max(int(elapsed_seconds), 0), MAX_STUDY_TICK_SECONDS)

    with db.transaction() as conn:
        _ensure_progress(conn, user_id)
        progress = _progress_row_for_update(conn, user_id)
        levels = _upgrade_levels_for_update(conn, user_id)
        rate = coin_rate_per_minute(levels)

        total_unpaid_seconds = progress["unpaid_seconds"] + seconds
        payable_minutes, remaining_seconds = divmod(total_unpaid_seconds, 60)
        coins_awarded = payable_minutes * rate

        conn.execute(
            "UPDATE user_progress SET "
            "coins = coins + ?, earned_coins = earned_coins + ?, "
            "study_seconds = study_seconds + ?, unpaid_seconds = ?, updated_at = ? "
            "WHERE user_id = ?",
            (coins_awarded, coins_awarded, seconds, remaining_seconds, now_utc().isoformat(), user_id),
        )

    plant_svc.apply_study_tick(user_id, seconds)
    return {
        "coins_awarded": coins_awarded,
        "state": get_shop_state(user_id),
        "plant": plant_svc.get_plant_state(user_id),
    }


def purchase_upgrade(user_id: int, upgrade_id: str) -> dict:
    upgrade = SHOP_BY_ID.get(upgrade_id)
    if upgrade is None:
        raise HTTPException(status_code=404, detail="Upgrade not found")

    with db.transaction() as conn:
        _ensure_progress(conn, user_id)
        current_level = _upgrade_level_for_update(conn, user_id, upgrade.id)
        cost = upgrade.next_cost(current_level)
        if cost is None:
            raise HTTPException(status_code=400, detail="Upgrade is already maxed")

        now = now_utc().isoformat()
        cur = conn.execute(
            "UPDATE user_progress SET coins = coins - ?, updated_at = ? "
            "WHERE user_id = ? AND coins >= ?",
            (cost, now, user_id, cost),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="Not enough coins")

        new_level = current_level + 1
        conn.execute(
            "INSERT INTO user_upgrades (user_id, upgrade_id, level, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, upgrade_id) DO UPDATE SET "
            "level = excluded.level, updated_at = excluded.updated_at",
            (user_id, upgrade.id, new_level, now),
        )

    return {
        "upgrade_id": upgrade.id,
        "level": new_level,
        "spent": cost,
        "state": get_shop_state(user_id),
    }


def award_learning_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, CARD_FOUNDRY)


def award_quiz_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, QUIZ_MAGNET)


def award_plan_bonus(user_id: int) -> int:
    return _award_upgrade_bonus(user_id, PLAN_COMPASS)


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
    coins = max(0, int(amount))
    with db.transaction() as conn:
        _ensure_progress(conn, user_id)
        if coins:
            conn.execute(
                "UPDATE user_progress SET coins = coins + ?, earned_coins = earned_coins + ?, updated_at = ? "
                "WHERE user_id = ?",
                (coins, coins, now_utc().isoformat(), user_id),
            )
    return get_shop_state(user_id)


def coin_rate_per_minute(levels: dict[str, int]) -> int:
    return BASE_COIN_RATE_PER_MINUTE + levels.get(FOCUS_ENGINE, 0)


def _award_upgrade_bonus(user_id: int, upgrade_id: str) -> int:
    upgrade = SHOP_BY_ID[upgrade_id]
    level = _upgrade_levels(user_id).get(upgrade.id, 0)
    amount = level * upgrade.bonus_coins
    if amount:
        grant_coins(user_id, amount)
    return amount


def _ensure_progress(conn, user_id: int) -> None:
    now = now_utc().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO user_progress "
        "(user_id, coins, earned_coins, study_seconds, unpaid_seconds, created_at, updated_at) "
        "VALUES (?, 0, 0, 0, 0, ?, ?)",
        (user_id, now, now),
    )


def _progress_row(user_id: int):
    row = db.query_one("SELECT * FROM user_progress WHERE user_id = ?", (user_id,))
    if row is None:
        ensure_progress(user_id)
        row = db.query_one("SELECT * FROM user_progress WHERE user_id = ?", (user_id,))
    if row is None:
        raise RuntimeError(f"Progress row could not be created for user {user_id}")
    return row


def _progress_row_for_update(conn, user_id: int):
    row = conn.execute("SELECT * FROM user_progress WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"Progress row not found for user {user_id}")
    return row


def _upgrade_levels(user_id: int) -> dict[str, int]:
    rows = db.query_all(
        "SELECT upgrade_id, level FROM user_upgrades WHERE user_id = ?",
        (user_id,),
    )
    return {row["upgrade_id"]: row["level"] for row in rows}


def _upgrade_levels_for_update(conn, user_id: int) -> dict[str, int]:
    rows = conn.execute(
        "SELECT upgrade_id, level FROM user_upgrades WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["upgrade_id"]: row["level"] for row in rows}


def _upgrade_level_for_update(conn, user_id: int, upgrade_id: str) -> int:
    row = conn.execute(
        "SELECT level FROM user_upgrades WHERE user_id = ? AND upgrade_id = ?",
        (user_id, upgrade_id),
    ).fetchone()
    return row["level"] if row else 0


def _serialize_upgrade(upgrade: Upgrade, level: int, coins: int) -> dict:
    level = max(0, level)
    next_cost = upgrade.next_cost(level)
    return {
        "id": upgrade.id,
        "name": upgrade.name,
        "description": upgrade.description,
        "effect_label": upgrade.effect_label,
        "level": min(level, upgrade.max_level),
        "max_level": upgrade.max_level,
        "next_cost": next_cost,
        "affordable": next_cost is not None and coins >= next_cost,
        "maxed": next_cost is None,
    }
