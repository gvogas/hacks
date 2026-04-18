def _upload(client, headers, content: bytes, filename: str, session_id: str | None = None):
    files = {"file": (filename, content, "text/plain")}
    data = {"session_id": session_id} if session_id else {}
    return client.post("/api/upload", headers=headers, files=files, data=data)


def test_upload_requires_auth(client):
    r = _upload(client, {}, b"hello", "notes.txt")
    assert r.status_code == 401


def test_upload_valid_txt_creates_session(client, user):
    r = _upload(client, user["headers"], b"hello world", "notes.txt")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["char_count"] == len(b"hello world")
    assert "hello world" in body["preview"]


def test_upload_rejects_bad_extension(client, user):
    r = _upload(client, user["headers"], b"irrelevant", "notes.exe")
    assert r.status_code == 400


def test_upload_appends_to_existing_session(client, user):
    first = _upload(client, user["headers"], b"one", "a.txt").json()
    sid = first["session_id"]
    _upload(client, user["headers"], b"two", "b.txt", session_id=sid)

    full = client.get(f"/api/study/session/{sid}", headers=user["headers"]).json()
    assert full["uploaded_texts"] == ["one", "two"]


def test_upload_with_foreign_session_id_falls_back_to_new_session(client, user, other_user):
    # Alice creates a session by uploading
    alice_sid = _upload(client, user["headers"], b"alice", "a.txt").json()["session_id"]

    # Bob passes Alice's session_id. ensure_session does not see it under Bob's user_id,
    # so Bob gets a brand-new session — Alice's data is never touched.
    r = _upload(client, other_user["headers"], b"bob", "b.txt", session_id=alice_sid)
    assert r.status_code == 200
    assert r.json()["session_id"] != alice_sid

    # Alice's session still has only her file
    alice_full = client.get(f"/api/study/session/{alice_sid}", headers=user["headers"]).json()
    assert alice_full["uploaded_texts"] == ["alice"]
