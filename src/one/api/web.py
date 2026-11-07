"""Server-rendered web UI: setup (superusuário), login, and the app shell.

No build step, no SPA — just HTML the API renders. The session is a signed JWT
(same one.identity.security helper the API uses) stored in an httponly cookie.
This is the Fase-0 shell; the rich SPA replaces these pages later without
changing the API underneath.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from one.api import ui
from one.api.deps import current_tenant, db_session
from one.config import get_settings
from one.identity.models import User
from one.identity.security import Principal, decode_token, issue_token
from one.identity.service import authenticate, create_user, has_any_user, user_count
from one.tenancy.context import TenantContext

router = APIRouter(tags=["web"], include_in_schema=False)
_settings = get_settings()
SESSION_COOKIE = "one_session"


# --------------------------------------------------------------------------- helpers
def _session(request: Request, tenant: TenantContext) -> Principal | None:
    tok = request.cookies.get(SESSION_COOKIE)
    if not tok:
        return None
    try:
        p = decode_token(tok)
    except Exception:
        return None
    return p if p.tenant == tenant.slug else None


def _set_session(resp: RedirectResponse, principal: Principal) -> None:
    token = issue_token(principal, ttl_seconds=60 * 60 * 12)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=60 * 60 * 12,
        httponly=True,
        samesite="lax",
        secure=_settings.is_prod,
        path="/",
    )


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


# --------------------------------------------------------------------------- routes
@router.get("/", response_class=HTMLResponse)
async def home(request: Request, tenant: TenantContext = Depends(current_tenant)):
    return _redirect("/app")


@router.get("/setup", response_class=HTMLResponse)
async def setup_form(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    if await has_any_user(session):
        return _redirect("/login")
    return HTMLResponse(ui.auth_page("Setup", ui.setup_body(tenant_slug=tenant.slug)))


@router.post("/setup")
async def setup_submit(
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if await has_any_user(session):
        return _redirect("/login")
    user = await create_user(
        session, email=email, password=password, full_name=full_name, is_admin=True
    )
    resp = _redirect("/app")
    _set_session(
        resp, Principal(user_id=str(user.id), tenant=tenant.slug, email=user.email, is_admin=True)
    )
    return resp


@router.get("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
    erro: str = "",
):
    if not await has_any_user(session):
        return _redirect("/setup")
    if _session(request, tenant):
        return _redirect("/app")
    return HTMLResponse(ui.auth_page("Entrar", ui.login_body(error=bool(erro))))


@router.post("/login")
async def login_submit(
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
    email: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate(session, email=email, password=password)
    if user is None:
        return _redirect("/login?erro=1")
    resp = _redirect("/app")
    _set_session(
        resp,
        Principal(
            user_id=str(user.id), tenant=tenant.slug, email=user.email, is_admin=user.is_admin
        ),
    )
    return resp


@router.get("/logout")
async def logout(tenant: TenantContext = Depends(current_tenant)):
    resp = _redirect("/login")
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/app", response_class=HTMLResponse)
async def app_home(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    if not await has_any_user(session):
        return _redirect("/setup")
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    total = await user_count(session)
    me = await session.get(User, principal.user_id)
    name = (me.full_name if me else None) or (principal.email or "").split("@")[0]
    body = ui.dashboard_body(tenant_slug=tenant.slug, users=total, user_name=name)
    return HTMLResponse(
        ui.shell(
            tenant_slug=tenant.slug, user_email=principal.email or "", active="Início", body=body
        )
    )


@router.get("/app/inbox", response_class=HTMLResponse)
async def inbox_page(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    body = ui.inbox_body(demo=True)
    return HTMLResponse(
        ui.shell(
            tenant_slug=tenant.slug,
            user_email=principal.email or "",
            active="Atendimento",
            body=body,
            full=True,
        )
    )


@router.get("/app/crm", response_class=HTMLResponse)
async def crm_page(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    return HTMLResponse(
        ui.shell(
            tenant_slug=tenant.slug,
            user_email=principal.email or "",
            active="CRM",
            body=ui.crm_body(),
            full=True,
        )
    )


@router.get("/app/inventory", response_class=HTMLResponse)
async def inventory_page(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    return HTMLResponse(
        ui.shell(
            tenant_slug=tenant.slug,
            user_email=principal.email or "",
            active="Inventário",
            body=ui.inventory_body(),
            full=True,
        )
    )


@router.post("/app/inbox/simular")
async def inbox_simulate(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
):
    """Demo: inject an inbound message through the real pipeline (webhook → stream).

    Ensures a demo webchat channel exists, then enqueues a message exactly as a
    provider webhook would, so the worker persists it and the gateway pushes it
    live. Lets you watch the realtime loop before a real channel is wired.
    """
    import random

    from sqlalchemy import select as _select

    from one.comms.bus import enqueue_inbound
    from one.comms.models import Channel, ChannelType

    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    channel = await session.scalar(
        _select(Channel).where(Channel.type == ChannelType.webchat).limit(1)
    )
    if channel is None:
        channel = Channel(type=ChannelType.webchat, name="Webchat (demo)", external_id="demo")
        session.add(channel)
        await session.flush()
    await session.commit()
    names = ["Visitante", "Cliente novo", "Maria", "João", "Padaria Zélia", "Auto Center"]
    greetings = [
        "Olá, bom dia!",
        "Vocês atendem hoje?",
        "Quero um orçamento",
        "Me liga?",
        "Tudo bem?",
    ]
    await enqueue_inbound(
        tenant.slug,
        str(channel.id),
        {
            "address": "web-" + str(random.randint(1000, 9999)),
            "name": random.choice(names),
            "body": random.choice(greetings),
            "provider_message_id": "demo-" + str(random.randint(100000, 999999)),
        },
    )
    return {"status": "queued"}


@router.get("/app/usuarios", response_class=HTMLResponse)
async def users_page(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
    erro: str = "",
):
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    rows = (await session.scalars(select(User).order_by(User.created_at))).all()
    users = [{"name": u.full_name, "email": u.email, "is_admin": u.is_admin} for u in rows]
    body = ui.users_body(users=users, error=bool(erro))
    return HTMLResponse(
        ui.shell(
            tenant_slug=tenant.slug, user_email=principal.email or "", active="Usuários", body=body
        )
    )


@router.post("/app/usuarios")
async def users_create(
    request: Request,
    tenant: TenantContext = Depends(current_tenant),
    session: AsyncSession = Depends(db_session),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
):
    principal = _session(request, tenant)
    if principal is None:
        return _redirect("/login")
    existing = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if existing is not None:
        return _redirect("/app/usuarios?erro=1")
    await create_user(
        session, email=email, password=password, full_name=full_name or None, is_admin=False
    )
    return _redirect("/app/usuarios")
