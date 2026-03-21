import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_item(min_quantity: float = 0):
    name = f"stage1-item-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/items",
        data={"name": name, "description": "", "unit": "个", "min_quantity": min_quantity},
    )
    assert resp.status_code == 200
    payload = resp.json()
    return payload["id"], name


def _delete_item(item_id: int):
    client.delete(f"/api/items/{item_id}")


def test_adjust_inventory_updates_quantity_and_rejects_negative():
    item_id, _ = _create_item()
    try:
        resp = client.put(
            f"/api/items/{item_id}/adjust",
            data={"adjusted_quantity": 3.5, "reason": "盘点"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["adjusted_quantity"] == 3.5

        detail = client.get(f"/api/items/{item_id}")
        assert detail.status_code == 200
        assert detail.json()["current_quantity"] == 3.5

        bad = client.put(f"/api/items/{item_id}/adjust", data={"adjusted_quantity": -1})
        assert bad.status_code == 400
    finally:
        _delete_item(item_id)


def test_low_stock_alerts_and_shopping_list_workflow():
    item_id, name = _create_item(min_quantity=5)
    try:
        low_stock = client.get("/api/alerts/low-stock")
        assert low_stock.status_code == 200
        alert_names = [x["name"] for x in low_stock.json()]
        assert name in alert_names

        generated = client.post(
            "/api/shopping-list/generate",
            data={"lookback_days": 30, "coverage_days": 14},
        )
        assert generated.status_code == 200
        payload = generated.json()
        assert payload["count"] >= 1

        items = client.get("/api/shopping-list?status=pending")
        assert items.status_code == 200
        pending = [x for x in items.json() if x["item_id"] == item_id]
        assert pending
        row_id = pending[0]["id"]

        updated = client.put(f"/api/shopping-list/{row_id}", data={"status": "purchased", "note": "已下单"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "purchased"

        purchased = client.get("/api/shopping-list?status=purchased")
        assert purchased.status_code == 200
        purchased_ids = [x["id"] for x in purchased.json()]
        assert row_id in purchased_ids

        bad_status = client.put(f"/api/shopping-list/{row_id}", data={"status": "unknown"})
        assert bad_status.status_code == 400
    finally:
        _delete_item(item_id)
