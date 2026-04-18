def test_shop_state_defaults(client, user):
    r = client.get("/api/shop/state", headers=user["headers"])
    assert r.status_code == 200

    body = r.json()
    assert body["coins"] == 0
    assert body["earned_coins"] == 0
    assert body["study_seconds"] == 0
    assert body["coin_rate_per_minute"] == 2
    assert {u["id"] for u in body["upgrades"]} >= {"focus_engine", "card_foundry"}


def test_study_tick_awards_coins_over_time(client, user):
    r = client.post(
        "/api/shop/study-tick",
        headers=user["headers"],
        json={"elapsed_seconds": 60},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["coins_awarded"] == 2
    assert body["state"]["coins"] == 2
    assert body["state"]["study_seconds"] == 60


def test_study_tick_banks_partial_minutes(client, user):
    first = client.post(
        "/api/shop/study-tick",
        headers=user["headers"],
        json={"elapsed_seconds": 45},
    ).json()
    assert first["coins_awarded"] == 0
    assert first["state"]["seconds_until_next_coin"] == 15

    second = client.post(
        "/api/shop/study-tick",
        headers=user["headers"],
        json={"elapsed_seconds": 20},
    ).json()
    assert second["coins_awarded"] == 2
    assert second["state"]["coins"] == 2
    assert second["state"]["study_seconds"] == 65


def test_purchase_upgrade_spends_coins_and_changes_rate(client, user):
    from services import shop

    shop.grant_coins(user["user"]["id"], 40)
    r = client.post(
        "/api/shop/purchase",
        headers=user["headers"],
        json={"upgrade_id": "focus_engine"},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["spent"] == 40
    assert body["level"] == 1
    assert body["state"]["coins"] == 0
    assert body["state"]["coin_rate_per_minute"] == 3

    tick = client.post(
        "/api/shop/study-tick",
        headers=user["headers"],
        json={"elapsed_seconds": 60},
    ).json()
    assert tick["coins_awarded"] == 3


def test_purchase_upgrade_requires_enough_coins(client, user):
    r = client.post(
        "/api/shop/purchase",
        headers=user["headers"],
        json={"upgrade_id": "focus_engine"},
    )
    assert r.status_code == 400
    assert "Not enough coins" in r.json()["detail"]


def test_learning_bonus_uses_card_foundry_upgrade(client, user, stub_agents):
    from services import shop

    shop.grant_coins(user["user"]["id"], 55)
    purchase = client.post(
        "/api/shop/purchase",
        headers=user["headers"],
        json={"upgrade_id": "card_foundry"},
    )
    assert purchase.status_code == 200

    sid = client.post(
        "/api/study/start",
        headers=user["headers"],
        json={"topic": "Waves"},
    ).json()["session_id"]
    r = client.post(
        "/api/study/generate-learning",
        headers=user["headers"],
        json={"session_id": sid, "num_flashcards": 1, "num_questions": 1},
    )
    assert r.status_code == 200
    assert r.json()["coins_awarded"] == 4

    state = client.get("/api/shop/state", headers=user["headers"]).json()
    assert state["coins"] == 4
