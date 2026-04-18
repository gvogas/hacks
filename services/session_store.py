import uuid
import json
import os
from datetime import datetime

_sessions: dict = {}
_PERSIST_FILE = "sessions.json"


def create_session() -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "topic": None,
        "notes": None,
        "uploaded_texts": [],
        "flashcards": [],
        "quiz_questions": [],
        "quiz_history": [],
        "study_plan": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    _persist()
    return session_id


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def update_session(session_id: str, data: dict):
    if session_id not in _sessions:
        return
    _sessions[session_id].update(data)
    _persist()


def ensure_session(session_id: str | None) -> str:
    if session_id and session_id in _sessions:
        return session_id
    return create_session()


def _persist():
    try:
        with open(_PERSIST_FILE, "w") as f:
            json.dump(_sessions, f)
    except Exception:
        pass


def _load():
    if os.path.exists(_PERSIST_FILE):
        try:
            with open(_PERSIST_FILE) as f:
                _sessions.update(json.load(f))
        except Exception:
            pass


_load()
