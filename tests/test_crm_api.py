"""CRM REST surface through the real app: auth → create deal → board → move → won.

Confirms the router is wired (lazy include) and the full HTTP path works.
Skipped unless ONE_TEST_DATABASE_URL is set.
"""

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


async def test_crm_board_and_deal_flow(provisioned_tenant):
    c = _client(provisioned_tenant)
    r = c.post(
        "/setup",
        data={"full_name": "Alex", "email": "[email protected]", "password": "segredo123"},
    )
    sess = r.cookies

    # empty board shows the default stages
    board = c.get("/crm/board", cookies=sess).json()
    assert [col["name"] for col in board["columns"]][:2] == ["Novo", "Qualificado"]
    assert board["stats"]["open_count"] == 0

    # create a deal
    created = c.post(
        "/crm/deals",
        json={"name": "Plano PRO - Loja Modelo", "value": "2500,00"},
        cookies=sess,
    )
    assert created.status_code == 200
    deal_id = created.json()["id"]

    # it appears on the board with pt-BR money parsed correctly
    board = c.get("/crm/board", cookies=sess).json()
    novo = board["columns"][0]
    assert novo["deals"][0]["value"] == "2500.00"
    assert board["stats"]["open_value"] == "2500.00"

    # add + complete an activity
    act = c.post(
        f"/crm/deals/{deal_id}/activities",
        json={"subject": "Enviar contrato", "kind": "email"},
        cookies=sess,
    ).json()
    done = c.post(f"/crm/activities/{act['id']}/complete", cookies=sess).json()
    assert done["done"] is True

    # move to the Proposta stage
    stage_proposta = next(col["id"] for col in board["columns"] if col["name"] == "Proposta")
    moved = c.post(
        f"/crm/deals/{deal_id}/move", json={"stage_id": stage_proposta}, cookies=sess
    ).json()
    assert moved["stage_id"] == stage_proposta

    # lost-reasons endpoint works after its internal ensure/commit (search_path regression)
    reasons = c.get("/crm/lost-reasons", cookies=sess).json()
    assert reasons and any(r["name"] == "Preço" for r in reasons)

    # win it → leaves the open board, win rate 100%
    won = c.post(f"/crm/deals/{deal_id}/won", cookies=sess).json()
    assert won["status"] == "won"
    board = c.get("/crm/board", cookies=sess).json()
    assert all(not col["deals"] for col in board["columns"])
    assert board["stats"]["win_rate"] == 100


async def test_crm_contacts(provisioned_tenant):
    c = _client(provisioned_tenant)
    r = c.post(
        "/setup",
        data={"full_name": "Alex", "email": "[email protected]", "password": "segredo123"},
    )
    sess = r.cookies
    made = c.post(
        "/crm/contacts",
        json={"name": "Loja Modelo LTDA", "kind": "company", "doc": "12345678000190"},
        cookies=sess,
    )
    assert made.status_code == 200
    cid = made.json()["id"]
    listing = c.get("/crm/contacts?q=Modelo", cookies=sess).json()
    assert any(p["id"] == cid for p in listing)
    detail = c.get(f"/crm/contacts/{cid}", cookies=sess).json()
    assert detail["kind"] == "company" and detail["doc"] == "12345678000190"
