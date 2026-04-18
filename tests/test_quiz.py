"""
Quiz grading tests.

Exercises the submit endpoint directly against a session seeded with known
quiz questions, so agent stubs aren't required for the grading path.
"""
import pytest


QUESTIONS = [
    {"id": 0, "question": "2+2?", "options": ["A) 3", "B) 4"], "answer": "B", "explanation": "math", "topic_tag": "Math"},
    {"id": 1, "question": "Sky?",  "options": ["A) Blue", "B) Red"], "answer": "A", "explanation": "sky", "topic_tag": "Science"},
    {"id": 2, "question": "2+3?",  "options": ["A) 5", "B) 6"], "answer": "A", "explanation": "math", "topic_tag": "Math"},
]


@pytest.fixture
def quiz_session(client, user):
    from services import session_store

    sid = session_store.create_session(user["user"]["id"])
    session_store.update_session(sid, user["user"]["id"], {
        "topic": "Quiz fixture",
        "notes": {"summary": "stub"},
        "quiz_questions": QUESTIONS,
    })
    return sid


def _submit(client, headers, sid, answers):
    return client.post("/api/quiz/submit", headers=headers, json={"session_id": sid, "answers": answers})


def test_perfect_score(client, user, quiz_session):
    r = _submit(client, user["headers"], quiz_session, [
        {"question_id": 0, "selected": "B"},
        {"question_id": 1, "selected": "A"},
        {"question_id": 2, "selected": "A"},
    ])
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 3
    assert body["total"] == 3
    assert body["percentage"] == 100.0
    assert body["weak_topics"] == []


def test_partial_score_identifies_weak_topics(client, user, quiz_session):
    r = _submit(client, user["headers"], quiz_session, [
        {"question_id": 0, "selected": "A"},  # wrong (Math)
        {"question_id": 1, "selected": "A"},  # right
        {"question_id": 2, "selected": "B"},  # wrong (Math)
    ])
    body = r.json()
    assert body["score"] == 1
    assert body["total"] == 3
    assert "Math" in body["weak_topics"]
    assert "Science" not in body["weak_topics"]


def test_answer_case_and_whitespace_normalized(client, user, quiz_session):
    r = _submit(client, user["headers"], quiz_session, [
        {"question_id": 0, "selected": " b "},  # lowercase + padding
        {"question_id": 1, "selected": "a"},
        {"question_id": 2, "selected": "A"},
    ])
    assert r.json()["score"] == 3


def test_missing_answers_count_as_wrong(client, user, quiz_session):
    # Only answer question 1 — questions 0 and 2 should be graded as wrong, not skipped.
    r = _submit(client, user["headers"], quiz_session, [
        {"question_id": 1, "selected": "A"},
    ])
    body = r.json()
    assert body["total"] == 3
    assert body["score"] == 1
    # Unanswered questions appear in results with empty selected
    unanswered = [res for res in body["results"] if res["question_id"] in (0, 2)]
    assert len(unanswered) == 2
    assert all(res["selected"] == "" and not res["is_correct"] for res in unanswered)


def test_submit_with_no_quiz_returns_400(client, user):
    from services import session_store

    sid = session_store.create_session(user["user"]["id"])
    r = _submit(client, user["headers"], sid, [{"question_id": 0, "selected": "A"}])
    assert r.status_code == 400


def test_submit_requires_auth(client, quiz_session):
    r = _submit(client, {}, quiz_session, [{"question_id": 0, "selected": "A"}])
    assert r.status_code == 401


def test_submit_other_users_session_rejected(client, user, other_user, quiz_session):
    # quiz_session belongs to `user`; `other_user` should get 404
    r = _submit(client, other_user["headers"], quiz_session, [{"question_id": 0, "selected": "B"}])
    assert r.status_code == 404


def test_quiz_history_recorded(client, user, quiz_session):
    _submit(client, user["headers"], quiz_session, [
        {"question_id": 0, "selected": "A"},
        {"question_id": 1, "selected": "A"},
        {"question_id": 2, "selected": "A"},
    ])
    full = client.get(f"/api/study/session/{quiz_session}", headers=user["headers"]).json()
    assert len(full["quiz_history"]) == 1
    entry = full["quiz_history"][0]
    assert entry["score"] == 2  # questions 1 and 2 right
    assert entry["total"] == 3
    assert entry["wrong_question_ids"] == [0]
