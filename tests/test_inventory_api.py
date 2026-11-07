"""Inventory REST through the real app: product → move → stats → insufficient block."""

from __future__ import annotations

import os

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("ONE_TEST_DATABASE_URL"), reason="ONE_TEST_DATABASE_URL not set"
)


def _client(slug: str) -> TestClient:
    from one.main import create_app

    c = TestClient(create_app(), follow_redirects=False)
    c.headers.update({"Host": f"{slug}.nettcom.io"})
    return c


async def test_inventory_flow(provisioned_tenant):
    c = _client(provisioned_tenant)
    r = c.post(
        "/setup",
        data={"full_name": "Alex", "email": "[email protected]", "password": "segredo123"},
    )
    sess = r.cookies

    prod = c.post(
        "/inv/products",
        json={"name": "Cabo HDMI", "sku": "CAB-1", "price": "39,90", "cost": "12,00", "min_stock": "5"},
        cookies=sess,
    )
    assert prod.status_code == 200
    pid = prod.json()["id"]

    # entrada 50
    mv = c.post(
        "/inv/moves",
        json={"product_id": pid, "kind": "in", "quantity": "50", "unit_cost": "12,00", "reason": "NF 1"},
        cookies=sess,
    )
    assert mv.status_code == 200 and mv.json()["balance_after"] == "50"

    # table shows it in stock with ok status and pt-BR price
    rows = c.get("/inv/products", cookies=sess).json()
    row = next(p for p in rows if p["id"] == pid)
    assert row["on_hand"] == "50" and row["status"] == "ok" and row["price"] == "39.90"

    # warehouses endpoint works after its internal ensure/commit (search_path regression)
    whs = c.get("/inv/warehouses", cookies=sess).json()
    assert whs and any(w["is_default"] for w in whs)

    # stats: 1 SKU, value 50*12 = 600
    st = c.get("/inv/stats", cookies=sess).json()
    assert st["sku_count"] == 1 and st["stock_value"] == "600.00"

    # oversell blocked
    bad = c.post(
        "/inv/moves", json={"product_id": pid, "kind": "out", "quantity": "999"}, cookies=sess
    )
    assert bad.status_code == 409

    # sell 46 -> below min (5) -> low
    c.post("/inv/moves", json={"product_id": pid, "kind": "out", "quantity": "46"}, cookies=sess)
    rows = c.get("/inv/products", cookies=sess).json()
    assert next(p for p in rows if p["id"] == pid)["status"] == "low"
