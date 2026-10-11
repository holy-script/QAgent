import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SHOP_DIR = Path(__file__).parents[2] / "demo-shop"


@pytest.fixture
def shop():
    spec = importlib.util.spec_from_file_location("demo_shop_main", SHOP_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_shop_main"] = module
    spec.loader.exec_module(module)
    return module, TestClient(module.app)


def test_bug1_badge_counts_lines_not_quantity(shop):
    module, client = shop
    client.post("/api/cart/add", json={"id": 1, "qty": 2})
    assert client.get("/api/cart").json()["count"] == 2
    assert 'data-testid="cart-badge" id="cart-badge">1<' in client.get("/products").text
    client.post("/__bugs", json={"1": False})
    assert 'id="cart-badge">2<' in client.get("/products").text


def test_bug2_postal_validation_toggle(shop):
    _, client = shop
    assert client.post("/api/checkout", json={"postal_code": "abc"}).status_code == 200
    client.post("/__bugs", json={"2": False})
    assert client.post("/api/checkout", json={"postal_code": "abc"}).status_code == 400
    assert client.post("/api/checkout", json={"postal_code": "12345"}).status_code == 200


def test_bug3_every_third_payment_fails_and_reset_clears_counter(shop):
    _, client = shop
    assert [client.post("/api/pay", json={}).status_code for _ in range(3)] == [200, 200, 500]
    client.post("/__reset")
    assert [client.post("/api/pay", json={}).status_code for _ in range(3)] == [200, 200, 500]
    client.post("/__bugs", json={"3": False})
    assert all(client.post("/api/pay", json={}).status_code == 200 for _ in range(6))


def test_bug5_tax_before_discount(shop):
    _, client = shop
    client.post("/api/cart/add", json={"id": 1, "qty": 2})
    client.post("/api/coupon", json={"code": "SAVE10"})
    buggy = client.get("/api/cart").json()
    assert buggy["total"] == round(198 * 1.08 - 19.8, 2)
    client.post("/__bugs", json={"5": False})
    assert client.get("/api/cart").json()["total"] == round((198 - 19.8) * 1.08, 2)


def test_expired_coupon_rejected(shop):
    _, client = shop
    assert client.post("/api/coupon", json={"code": "EXPIRED10"}).status_code == 400
