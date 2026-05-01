from conftest import SERVER_BASE_URL, APIClient, place_order


def test_get_shops_returns_all_configured_shops(api_client):
    resp = api_client.get("/api/shops")
    assert resp.status_code == 200
    shops = resp.json()
    assert len(shops) == 2
    shop_ids = {s["shop_id"] for s in shops}
    assert "SHOP-001" in shop_ids
    assert "SHOP-002" in shop_ids


def test_get_shops_contains_items(api_client):
    resp = api_client.get("/api/shops")
    shops = resp.json()
    shop_001 = next(s for s in shops if s["shop_id"] == "SHOP-001")
    assert len(shop_001["items"]) == 2
    item_names = {i["name"] for i in shop_001["items"]}
    assert "Coffee" in item_names
    assert "Sandwich" in item_names


def test_get_orders_empty_for_new_session(fresh_session):
    resp = fresh_session.get("/api/orders")
    assert resp.status_code == 200
    assert resp.json() == []


def test_place_order_success(fresh_session):
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    order = resp.json()
    assert "order_id" in order
    assert order["order_id"].startswith("ORD-")
    assert order["shop_name"] == "Midtbyen Convenience"
    assert order["status"] in ("pending", "calculating_route", "dispatched")
    assert order["drone"]["drone_id"] in ("1", "2")


def test_place_order_assigns_closest_drone(fresh_session):
    resp = place_order(fresh_session, shop_id="SHOP-001", item_id="ITM-01")
    order = resp.json()
    assert order["drone"]["drone_id"] == "1"


def test_place_order_invalid_shop(fresh_session):
    resp = place_order(fresh_session, shop_id="SHOP-999")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_place_order_invalid_item(fresh_session):
    resp = place_order(fresh_session, shop_id="SHOP-001", item_id="ITM-999")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_get_order_after_placement(fresh_session):
    resp = place_order(fresh_session)
    order_id = resp.json()["order_id"]

    resp = fresh_session.get(f"/api/orders/{order_id}")
    assert resp.status_code == 200
    order = resp.json()
    assert order["order_id"] == order_id
    assert order["shop_id"] == "SHOP-001"


def test_get_order_not_found(fresh_session):
    resp = fresh_session.get("/api/orders/ORD-NONEXISTENT")
    assert resp.status_code == 404


def test_get_orders_returns_placed_orders(fresh_session):
    place_order(fresh_session, shop_id="SHOP-001", item_id="ITM-01")
    place_order(fresh_session, shop_id="SHOP-002", item_id="ITM-04")

    resp = fresh_session.get("/api/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 2
    shop_names = {o["shop_name"] for o in orders}
    assert "Midtbyen Convenience" in shop_names
    assert "Gloshaugen Market" in shop_names


def test_orders_isolated_between_sessions(api_client):
    s1 = api_client
    s2 = APIClient(SERVER_BASE_URL)

    place_order(s1)
    place_order(s1)

    resp_s1 = s1.get("/api/orders")
    resp_s2 = s2.get("/api/orders")

    assert len(resp_s1.json()) >= 2
    assert len(resp_s2.json()) == 0
