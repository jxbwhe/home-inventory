import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_token():
    name = f"shortcut-token-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/tokens", data={"name": name})
    assert resp.status_code == 200
    payload = resp.json()
    return payload["id"], payload["token"]


def _delete_token(token_id: int):
    client.delete(f"/api/tokens/{token_id}")


def _create_family(name: str):
    resp = client.post("/api/families", data={"name": name})
    assert resp.status_code == 200
    return resp.json()["id"]


def _delete_family(family_id: int):
    client.delete(f"/api/families/{family_id}")


def _create_item(name: str, family_id: int):
    resp = client.post(
        "/api/items",
        data={"name": name, "description": "", "unit": "个", "min_quantity": 1, "family_id": family_id},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _delete_item(item_id: int):
    client.delete(f"/api/items/{item_id}")


def test_shortcut_menu_and_quick_entry_purchase_usage():
    token_id = None
    family_id = None
    item_id = None
    try:
        token_id, token = _create_token()
        headers = {"x-api-token": token}
        family_id = _create_family(f"shortcut-family-{uuid.uuid4().hex[:8]}")
        item_id = _create_item(f"shortcut-item-{uuid.uuid4().hex[:8]}", family_id)

        menu = client.get(f"/openapi/shortcut/menu?family_id={family_id}", headers=headers)
        assert menu.status_code == 200
        payload = menu.json()
        assert any(a["value"] == "purchase" for a in payload["actions"])
        assert any(f["id"] == family_id for f in payload["families"])
        assert any(i["id"] == item_id for i in payload["items"])

        buy = client.post(
            "/openapi/quick-entry",
            headers=headers,
            json={"action": "purchase", "item_id": item_id, "quantity": 5, "price": 20},
        )
        assert buy.status_code == 200
        assert buy.json()["action"] == "purchase"
        assert buy.json()["current_quantity"] >= 5

        use = client.post(
            "/openapi/quick-entry",
            headers=headers,
            json={"action": "usage", "item_id": item_id, "quantity": 2},
        )
        assert use.status_code == 200
        assert use.json()["action"] == "usage"
        assert use.json()["current_quantity"] >= 3
    finally:
        if item_id is not None:
            _delete_item(item_id)
        if family_id is not None:
            _delete_family(family_id)
        if token_id is not None:
            _delete_token(token_id)


def test_quick_entry_requires_item_id_when_duplicate_names():
    token_id = None
    family_id = None
    item_1 = None
    item_2 = None
    dup_name = f"dup-item-{uuid.uuid4().hex[:6]}"
    try:
        token_id, token = _create_token()
        headers = {"x-api-token": token}
        family_id = _create_family(f"dup-family-{uuid.uuid4().hex[:8]}")
        item_1 = _create_item(dup_name, family_id)
        item_2 = _create_item(dup_name, family_id)

        resp = client.post(
            "/openapi/quick-entry",
            headers=headers,
            json={"action": "usage", "item_name": dup_name, "family_id": family_id, "quantity": 1},
        )
        assert resp.status_code == 400
    finally:
        if item_1 is not None:
            _delete_item(item_1)
        if item_2 is not None:
            _delete_item(item_2)
        if family_id is not None:
            _delete_family(family_id)
        if token_id is not None:
            _delete_token(token_id)
