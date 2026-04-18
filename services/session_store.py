import json
import uuid

from fastapi import HTTPException

from services import db
from services.auth import now_utc

_EMPTY = {
    "topic": None,
    "notes": None,
    "uploaded_texts": [],
    "flashcards": [],
    "quiz_questions": [],
    "quiz_history": [],
    "study_plan": None,
}


def create_session(user_id: int) -> str:
    session_id = str(uuid.uuid4())
    now = now_utc().isoformat()
    db.execute(
        "INSERT INTO sessions (id, user_id, topic, data, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user_id, None, json.dumps(_EMPTY), now, now),
    )
    return session_id


def get_session(session_id: str, user_id: int) -> dict | None:
    row = db.query_one(
        "SELECT data FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not row:
        return None
    return {**_EMPTY, **json.loads(row["data"])}


def require_session(session_id: str, user_id: int) -> dict:
    session = get_session(session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def ensure_session(session_id: str | None, user_id: int) -> str:
    if session_id and db.query_one(
        "SELECT 1 FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    ):
        return session_id
    return create_session(user_id)


def update_session(session_id: str, user_id: int, updates: dict):
    # Single round-trip: json_patch merges keys server-side; topic mirrored to its
    # own column so we can list/sort sessions without parsing the blob.
    db.execute(
        "UPDATE sessions SET data = json_patch(data, ?), "
        "topic = COALESCE(?, topic), updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (json.dumps(updates), updates.get("topic"), now_utc().isoformat(), session_id, user_id),
    )


def list_sessions(user_id: int) -> list[dict]:
    rows = db.query_all(
        "SELECT id, topic, created_at, updated_at FROM sessions "
        "WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    return [
        {
            "session_id": r["id"],
            "topic": r["topic"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def delete_session(session_id: str, user_id: int) -> bool:
    cur = db.execute(
        "DELETE FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    return cur.rowcount > 0
