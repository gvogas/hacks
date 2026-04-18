from datetime import timedelta
from urllib.parse import parse_qs, urlparse


def test_spotify_status_requires_auth(client):
    assert client.get("/api/spotify/status").status_code == 401


def test_spotify_status_defaults_to_not_connected(client, user):
    r = client.get("/api/spotify/status", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False
    assert body["display_name"] is None


def test_spotify_connect_requires_env(client, user, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    r = client.post("/api/spotify/connect", headers=user["headers"])

    assert r.status_code == 503
    assert "Spotify is not configured" in r.json()["detail"]


def test_spotify_callback_includes_error_detail(client):
    r = client.get("/api/spotify/callback", params={"code": "oauth-code"}, follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/?spotify=error&spotify_detail=Missing+Spotify+OAuth+state"


def test_spotify_oauth_callback_stores_connection(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/spotify/callback")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service

    def fake_token_request(_data, _settings):
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "scope": "user-read-private user-read-email",
            "token_type": "Bearer",
        }

    def fake_spotify_request(_method, path, _access_token, **_kwargs):
        assert path == "/me"
        return {"id": "spotify-user-1", "display_name": "Study DJ"}

    monkeypatch.setattr(spotify_service, "_token_request", fake_token_request)
    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    connect = client.post("/api/spotify/connect", headers=user["headers"])
    assert connect.status_code == 200
    auth_url = connect.json()["auth_url"]
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    callback = client.get(
        "/api/spotify/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?spotify=connected"

    status = client.get("/api/spotify/status", headers=user["headers"])
    assert status.status_code == 200
    body = status.json()
    assert body["connected"] is True
    assert body["display_name"] == "Study DJ"
    assert body["spotify_user_id"] == "spotify-user-1"

    row = db.query_one("SELECT access_token, refresh_token FROM spotify_connections WHERE user_id = ?", (user["user"]["id"],))
    assert row["access_token"] != "access-token"
    assert row["refresh_token"] != "refresh-token"
    assert row["access_token"].startswith("fernet:")
    assert row["refresh_token"].startswith("fernet:")
    assert spotify_service._decrypt_token(row["access_token"]) == "access-token"
    assert spotify_service._decrypt_token(row["refresh_token"]) == "refresh-token"


def test_spotify_play_uses_decrypted_token(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(method, path, access_token, **kwargs):
        assert method == "PUT"
        assert path == "/me/player/play"
        assert access_token == "access-token"
        assert kwargs == {"params": None, "json": None}
        return None

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.put("/api/spotify/play", headers=user["headers"])

    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_spotify_search_returns_tracks_and_playlists(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(method, path, access_token, **kwargs):
        assert method == "GET"
        assert path == "/search"
        assert access_token == "access-token"
        assert kwargs["params"]["q"] == "focus"
        assert kwargs["params"]["type"] == "track,playlist"
        return {
            "tracks": {
                "items": [
                    {
                        "id": "track-1",
                        "name": "Focus Song",
                        "uri": "spotify:track:track-1",
                        "artists": [{"name": "Artist"}],
                        "album": {"name": "Album", "images": [{"url": "https://image.example/track.jpg"}]},
                        "external_urls": {"spotify": "https://open.spotify.com/track/track-1"},
                    }
                ]
            },
            "playlists": {
                "items": [
                    {
                        "id": "playlist-1",
                        "name": "Focus Playlist",
                        "uri": "spotify:playlist:playlist-1",
                        "owner": {"display_name": "Owner"},
                        "tracks": {"total": 12},
                        "images": [{"url": "https://image.example/playlist.jpg"}],
                        "external_urls": {"spotify": "https://open.spotify.com/playlist/playlist-1"},
                    }
                ]
            },
        }

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.get("/api/spotify/search", params={"q": "focus"}, headers=user["headers"])

    assert r.status_code == 200
    body = r.json()
    assert body["tracks"][0]["name"] == "Focus Song"
    assert body["tracks"][0]["artist"] == "Artist"
    assert body["playlists"][0]["name"] == "Focus Playlist"
    assert body["playlists"][0]["tracks_total"] == 12


def test_spotify_play_accepts_device_id(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(method, path, access_token, **kwargs):
        assert method == "PUT"
        assert path == "/me/player/play"
        assert access_token == "access-token"
        assert kwargs == {
            "params": {"device_id": "device-1"},
            "json": {"uris": ["spotify:track:track-1"]},
        }
        return None

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.put(
        "/api/spotify/play",
        json={"device_id": "device-1", "uris": ["spotify:track:track-1"]},
        headers=user["headers"],
    )

    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_spotify_transfer_targets_device(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(method, path, access_token, **kwargs):
        assert method == "PUT"
        assert path == "/me/player"
        assert access_token == "access-token"
        assert kwargs == {"json": {"device_ids": ["device-1"], "play": False}}
        return None

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.put("/api/spotify/transfer", json={"device_id": "device-1"}, headers=user["headers"])

    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_spotify_current_returns_now_playing_summary(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(method, path, access_token, **kwargs):
        assert method == "GET"
        assert path == "/me/player"
        assert access_token == "access-token"
        assert kwargs == {}
        return {
            "is_playing": True,
            "progress_ms": 45000,
            "device": {"id": "device-1", "name": "Laptop", "type": "Computer"},
            "context": {"type": "playlist", "uri": "spotify:playlist:playlist-1"},
            "item": {
                "type": "track",
                "id": "track-1",
                "name": "Focus Song",
                "uri": "spotify:track:track-1",
                "duration_ms": 180000,
                "artists": [{"name": "Artist"}],
                "album": {"name": "Album", "images": [{"url": "https://image.example/track.jpg"}]},
                "external_urls": {"spotify": "https://open.spotify.com/track/track-1"},
            },
        }

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.get("/api/spotify/current", headers=user["headers"])

    assert r.status_code == 200
    body = r.json()
    assert body["is_playing"] is True
    assert body["progress_ms"] == 45000
    assert body["duration_ms"] == 180000
    assert body["device"]["name"] == "Laptop"
    assert body["item"]["name"] == "Focus Song"
    assert body["item"]["artist"] == "Artist"


def test_spotify_current_handles_no_playback(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    from services import db
    from services import spotify as spotify_service
    from services.auth import now_utc

    def fake_spotify_request(_method, _path, _access_token, **_kwargs):
        return None

    monkeypatch.setattr(spotify_service, "_spotify_request", fake_spotify_request)

    now = now_utc()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            spotify_service._encrypt_token("access-token"),
            spotify_service._encrypt_token("refresh-token"),
            (now + timedelta(hours=1)).isoformat(),
            now.isoformat(),
            now.isoformat(),
        ),
    )

    r = client.get("/api/spotify/current", headers=user["headers"])

    assert r.status_code == 200
    assert r.json()["is_playing"] is False
    assert r.json()["item"] is None


def test_spotify_disconnect_removes_connection(client, user, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")

    from services import db
    from services.auth import now_utc

    now = now_utc().isoformat()
    db.execute(
        "INSERT INTO spotify_connections "
        "(user_id, spotify_user_id, display_name, scope, token_type, access_token, refresh_token, "
        "expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["user"]["id"],
            "spotify-user-1",
            "Study DJ",
            "",
            "Bearer",
            "access-token",
            "refresh-token",
            now,
            now,
            now,
        ),
    )

    r = client.post("/api/spotify/disconnect", headers=user["headers"])

    assert r.status_code == 200
    assert r.json()["connected"] is False
