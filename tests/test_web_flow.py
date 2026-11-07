"""End-to-end web flow against a real Postgres: setup → login → app → users.

Skipped unless ONE_TEST_DATABASE_URL is set (the CI job provides one).
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


async def test_full_setup_login_flow(provisioned_tenant):
    slug = provisioned_tenant
    c = _client(slug)

    # No users yet → /app and /login send you to /setup
    assert c.get("/app").headers["location"] == "/setup"
    assert c.get("/login").headers["location"] == "/setup"
    assert "Criar superusuário" in c.get("/setup").text

    # Create the superuser
    r = c.post(
        "/setup",
        data={"full_name": "Alex", "email": "[email protected]", "password": "segredo123"},
    )
    assert r.status_code == 303 and r.headers["location"] == "/app"
    assert "one_session" in r.cookies

    # Authenticated shell renders
    app = c.get("/app", cookies=r.cookies)
    assert app.status_code == 200 and "Está no ar" in app.text

    # Setup is now closed; login is the door
    assert c.get("/setup").headers["location"] == "/login"

    # Wrong password bounces
    bad = c.post("/login", data={"email": "[email protected]", "password": "nope"})
    assert bad.headers["location"] == "/login?erro=1"

    # Right password logs in
    ok = c.post("/login", data={"email": "[email protected]", "password": "segredo123"})
    assert ok.status_code == 303 and ok.headers["location"] == "/app"

    # Add a second user, then it shows up in the list
    sess = ok.cookies
    add = c.post(
        "/app/usuarios",
        data={"full_name": "Maria", "email": "[email protected]", "password": "outrasenha9"},
        cookies=sess,
    )
    assert add.status_code == 303
    listing = c.get("/app/usuarios", cookies=sess).text
    assert "[email protected]" in listing and "[email protected]" in listing


async def test_app_requires_auth(provisioned_tenant):
    c = _client(provisioned_tenant)
    # create admin so we are past /setup
    c.post(
        "/setup",
        data={"full_name": "A", "email": "[email protected]", "password": "segredo123"},
    )
    # a fresh client with no cookie is pushed to /login
    c2 = _client(provisioned_tenant)
    assert c2.get("/app").headers["location"] == "/login"
