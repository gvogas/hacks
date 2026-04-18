def test_sessions_empty_for_new_user(client, user):
    r = client.get("/api/study/sessions", headers=user["headers"])
    assert r.status_code == 200
    assert r.json() == {"sessions": []}


def test_sessions_require_auth(client):
    assert client.get("/api/study/sessions").status_code == 401


def test_study_start_creates_session(client, user, stub_agents):
    r = client.post("/api/study/start", headers=user["headers"], json={"topic": "Photosynthesis"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    assert body["notes"]["summary"]

    sessions = client.get("/api/study/sessions", headers=user["headers"]).json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == body["session_id"]
    assert sessions[0]["topic"] == "Photosynthesis"


def test_session_get_returns_full_payload(client, user, stub_agents):
    sid = client.post("/api/study/start", headers=user["headers"], json={"topic": "Mitosis"}).json()["session_id"]

    r = client.get(f"/api/study/session/{sid}", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["topic"] == "Mitosis"
    assert body["notes"]["summary"]
    assert body["flashcards"] == []


def test_generate_learning_populates_flashcards_and_quiz(client, user, stub_agents):
    sid = client.post("/api/study/start", headers=user["headers"], json={"topic": "Waves"}).json()["session_id"]

    r = client.post(
        "/api/study/generate-learning",
        headers=user["headers"],
        json={"session_id": sid, "num_flashcards": 3, "num_questions": 2, "difficulty": "beginner"},
    )
    assert r.status_code == 200
    assert len(r.json()["flashcards"]) == 3
    assert len(r.json()["quiz_questions"]) == 2

    # Persisted on the session
    full = client.get(f"/api/study/session/{sid}", headers=user["headers"]).json()
    assert len(full["flashcards"]) == 3


def test_generate_learning_rejects_without_notes(client, user):
    # Create a session row directly with no notes, via a zero-topic study/start would hit agents.
    # Instead, call generate-learning with a bogus id -> 404 (different code path), so emulate the
    # "no notes" case by inserting a blank session via the store.
    from services import session_store

    sid = session_store.create_session(user["user"]["id"])
    r = client.post(
        "/api/study/generate-learning",
        headers=user["headers"],
        json={"session_id": sid, "num_flashcards": 1, "num_questions": 1, "difficulty": "intermediate"},
    )
    assert r.status_code == 400


def test_session_isolation_between_users(client, user, other_user, stub_agents):
    sid = client.post("/api/study/start", headers=user["headers"], json={"topic": "Alice topic"}).json()["session_id"]

    # Bob's session list does not include Alice's session
    r = client.get("/api/study/sessions", headers=other_user["headers"])
    assert r.json()["sessions"] == []

    # Bob cannot read Alice's session by id
    assert client.get(f"/api/study/session/{sid}", headers=other_user["headers"]).status_code == 404

    # Bob cannot delete Alice's session
    assert client.delete(f"/api/study/session/{sid}", headers=other_user["headers"]).status_code == 404

    # Alice's session still exists
    assert client.get(f"/api/study/session/{sid}", headers=user["headers"]).status_code == 200


def test_delete_session(client, user, stub_agents):
    sid = client.post("/api/study/start", headers=user["headers"], json={"topic": "Delete me"}).json()["session_id"]

    r = client.delete(f"/api/study/session/{sid}", headers=user["headers"])
    assert r.status_code == 200

    assert client.get(f"/api/study/session/{sid}", headers=user["headers"]).status_code == 404
    assert client.get("/api/study/sessions", headers=user["headers"]).json()["sessions"] == []


def test_delete_missing_session_returns_404(client, user):
    r = client.delete("/api/study/session/does-not-exist", headers=user["headers"])
    assert r.status_code == 404
