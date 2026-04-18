"""
Shared test fixtures.

Each test gets an isolated SQLite file and a fresh FastAPI app instance, so
tests never see each other's users or sessions.
"""
import os
import sys
from pathlib import Path

import pytest

# Secrets must be set before `services.auth` imports — it loads the JWT secret
# at module import. Using a stable test secret makes tokens deterministic.
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient backed by a throwaway SQLite file."""
    from fastapi.testclient import TestClient

    import services.db as dbmod

    # Reset any cached connection from a prior test and point at a fresh file.
    if dbmod._conn is not None:
        dbmod._conn.close()
        dbmod._conn = None
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test.db")

    from main import create_app

    with TestClient(create_app()) as c:
        yield c

    if dbmod._conn is not None:
        dbmod._conn.close()
        dbmod._conn = None


def _signup(client, email: str, password: str = "pw123456") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def user(client):
    data = _signup(client, "alice@example.com")
    return {"token": data["token"], "user": data["user"], "headers": {"Authorization": "Bearer " + data["token"]}}


@pytest.fixture
def other_user(client):
    data = _signup(client, "bob@example.com")
    return {"token": data["token"], "user": data["user"], "headers": {"Authorization": "Bearer " + data["token"]}}


@pytest.fixture
def stub_agents(monkeypatch):
    """Replace agent .run methods with deterministic stubs so tests don't hit Groq/Tavily."""
    from routers import plan as plan_router
    from routers import study as study_router

    async def fake_research(_topic):
        return [{"title": "stub", "content": "stub result"}]

    async def fake_content(topic, _search_results, _uploaded_texts):
        return {
            "summary": f"Summary about {topic}",
            "key_concepts": ["alpha", "beta"],
            "sections": [{"title": "Intro", "content": "body"}],
        }

    async def fake_learning(_notes, num_flashcards=10, num_questions=5, difficulty="intermediate"):
        return {
            "flashcards": [{"front": f"Q{i}", "back": f"A{i}"} for i in range(num_flashcards)],
            "quiz_questions": [
                {
                    "id": i,
                    "question": f"Question {i}?",
                    "options": ["A) one", "B) two", "C) three", "D) four"],
                    "answer": "A",
                    "explanation": "because",
                    "topic_tag": "General",
                }
                for i in range(num_questions)
            ],
        }

    async def fake_plan(**_kwargs):
        return {"plan": [{"day": 1, "focus": "Intro", "tasks": []}]}

    monkeypatch.setattr(study_router.research_agent, "run", fake_research)
    monkeypatch.setattr(study_router.content_agent, "run", fake_content)
    monkeypatch.setattr(study_router.learning_agent, "run", fake_learning)
    monkeypatch.setattr(plan_router.planning_agent, "run", fake_plan)
