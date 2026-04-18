def test_signup_returns_token_and_user(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["email"] == "a@b.com"
    assert "password" not in body["user"]


def test_duplicate_signup_returns_409(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123456"})
    r = client.post("/api/auth/signup", json={"email": "A@B.com", "password": "pw123456"})
    assert r.status_code == 409  # email normalized to lowercase


def test_signup_validates_email_format(client):
    r = client.post("/api/auth/signup", json={"email": "not-an-email", "password": "pw123456"})
    assert r.status_code == 422


def test_signup_rejects_short_password(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "abc"})
    assert r.status_code == 422


def test_login_success(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123456"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw123456"})
    assert r.status_code == 200
    assert r.json()["token"]


def test_login_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123456"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "WRONG"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@b.com", "password": "pw123456"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_user(client, user):
    r = client.get("/api/auth/me", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["user"]["email"] == user["user"]["email"]


def test_invalid_token_rejected(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401


def test_malformed_auth_header_rejected(client):
    r = client.get("/api/auth/me", headers={"Authorization": "NotBearer whatever"})
    assert r.status_code in (401, 403)  # HTTPBearer returns 403 for wrong scheme
