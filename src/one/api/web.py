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


# --------------------------------------------------------------------------- chrome
_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,sans-serif;color:#15171C;background:#F4F5F7}
a{color:#2456D6;text-decoration:none}a:hover{color:#1B44AD}
.wrap{display:flex;flex-wrap:wrap;min-height:100vh}
nav.side{width:232px;flex:0 0 232px;background:#0F1420;color:#C9CFDB;display:flex;flex-direction:column;padding:16px 12px;gap:4px;min-height:100vh}
nav.side a{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;color:#C9CFDB;font-size:13.5px}
nav.side a.on{background:#1C2436;color:#fff;font-weight:500}
nav.side a.muted{color:#8A93A6}
.brand{display:flex;align-items:center;gap:10px;padding:6px 8px 18px}
.logo{width:30px;height:30px;border-radius:8px;background:#2456D6;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700}
main{flex:999 1 560px;min-width:0;display:flex;flex-direction:column}
header.top{height:56px;background:#fff;border-bottom:1px solid #E3E6EC;display:flex;align-items:center;gap:16px;padding:0 20px}
.content{padding:24px 28px;display:flex;flex-direction:column;gap:20px;max-width:1100px}
.card{background:#fff;border:1px solid #E3E6EC;border-radius:12px;padding:18px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.kpi .n{font-size:26px;font-weight:600;letter-spacing:-.02em}
.kpi .l{font-size:12.5px;color:#6B7280}
label{font-size:12px;color:#6B7280;font-weight:500;display:block;margin-bottom:6px}
input{height:38px;border:1px solid #E3E6EC;border-radius:8px;padding:0 12px;font:inherit;font-size:14px;width:100%;color:#15171C}
button.primary{height:40px;border:0;border-radius:8px;background:#2456D6;color:#fff;font:inherit;font-size:14px;font-weight:600;padding:0 18px;cursor:pointer}
button.primary:hover{background:#1B44AD}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;color:#6B7280;font-size:12px;font-weight:500;padding:10px 12px}
td{padding:12px;border-top:1px solid #F0F2F5}
.pill{font-size:11px;border-radius:999px;padding:2px 8px;font-weight:600}
.err{background:#FEF2F2;color:#B91C1C;border:1px solid #FECACA;border-radius:8px;padding:10px 12px;font-size:13.5px}
.auth{max-width:380px;margin:9vh auto;display:flex;flex-direction:column;gap:18px;padding:0 20px}
.auth .card{display:flex;flex-direction:column;gap:14px}
h1{letter-spacing:-.01em}
"""

_NAV = [
    ("/app", "Início", True),
    ("/app", "CRM", False),
    ("/app", "Atendimento", False),
    ("/app", "Vendas", False),
    ("/app", "Financeiro", False),
    ("/app", "Fiscal", False),
    ("/app/usuarios", "Usuários", False),
]


def _shell(tenant: TenantContext, principal: Principal, active: str, body: str) -> str:
    links = ""
    for href, label, _is_home in _NAV:
        on = "on" if label == active else ""
        links += f'<a href="{href}" class="{on}">{label}</a>'
    initials = (principal.email or "?")[:2].upper()
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nettcom ONE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CSS}</style></head><body>
<div class="wrap">
  <nav class="side">
    <div class="brand"><div class="logo">N</div>
      <div><div style="color:#fff;font-weight:600;font-size:14px">Nettcom ONE</div>
      <div style="font-size:11px;color:#8A93A6">{tenant.slug}</div></div></div>
    {links}
    <div style="flex:1"></div>
    <div style="border-top:1px solid #1C2436;padding-top:12px;display:flex;align-items:center;gap:10px;padding-left:10px">
      <div style="width:28px;height:28px;border-radius:50%;background:#3A4A6B;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600">{initials}</div>
      <div style="flex:1"><div style="color:#fff;font-size:13px">{principal.email or "admin"}</div>
      <a href="/logout" style="font-size:11px;color:#8A93A6">Sair</a></div>
    </div>
  </nav>
  <main>
    <header class="top"><span style="font-size:13px;font-weight:600">{active}</span></header>
    <div class="content">{body}</div>
  </main>
</div></body></html>"""


def _auth_page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Nettcom ONE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CSS}</style></head><body>
<div class="auth">
  <div style="display:flex;align-items:center;gap:10px"><div class="logo">N</div>
    <span style="font-weight:600;font-size:16px">Nettcom ONE</span></div>
  {body}
</div></body></html>"""


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
    body = f"""<div class="card">
    <div><h1 style="margin:0 0 4px;font-size:20px">Criar superusuário</h1>
    <p style="margin:0;color:#6B7280;font-size:13.5px">Primeiro acesso do workspace <strong>{tenant.slug}</strong>.</p></div>
    <form method="post" action="/setup" style="display:flex;flex-direction:column;gap:14px">
      <div><label>Nome</label><input name="full_name" required autofocus></div>
      <div><label>E-mail</label><input name="email" type="email" required></div>
      <div><label>Senha</label><input name="password" type="password" minlength="8" required></div>
      <button class="primary" type="submit">Criar e entrar</button>
    </form></div>"""
    return HTMLResponse(_auth_page("Setup", body))


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
    err_html = '<div class="err">E-mail ou senha inválidos.</div>' if erro else ""
    body = f"""<div class="card">
    <h1 style="margin:0;font-size:20px">Entrar</h1>
    {err_html}
    <form method="post" action="/login" style="display:flex;flex-direction:column;gap:14px">
      <div><label>E-mail</label><input name="email" type="email" required autofocus></div>
      <div><label>Senha</label><input name="password" type="password" required></div>
      <button class="primary" type="submit">Entrar</button>
    </form></div>"""
    return HTMLResponse(_auth_page("Entrar", body))


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
    body = f"""<div style="display:flex;align-items:flex-end;gap:12px">
      <div><h1 style="margin:0;font-size:22px">Bem-vindo</h1>
      <p style="margin:4px 0 0;color:#6B7280;font-size:13.5px">Workspace {tenant.slug} · você é administrador</p></div></div>
    <div class="grid4">
      <div class="card kpi"><div class="l">Usuários</div><div class="n">{total}</div></div>
      <div class="card kpi"><div class="l">Oportunidades</div><div class="n">0</div></div>
      <div class="card kpi"><div class="l">Tickets abertos</div><div class="n">0</div></div>
      <div class="card kpi"><div class="l">A receber</div><div class="n">R$ 0</div></div>
    </div>
    <div class="card"><h2 style="margin:0 0 6px;font-size:16px">Está no ar 🎉</h2>
    <p style="margin:0;color:#6B7280;font-size:13.5px;line-height:1.5">Login, multi-tenant e o shell do app funcionando. Os módulos (CRM, Vendas, Fiscal…) entram a seguir, cada um já herdando permissões, auditoria e o agente de IA.
    Enquanto isso, a <a href="/docs">API</a> está documentada e você pode gerenciar <a href="/app/usuarios">usuários</a>.</p></div>"""
    return HTMLResponse(_shell(tenant, principal, "Início", body))


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
    trs = ""
    for u in rows:
        badge = (
            '<span class="pill" style="background:#EEF3FF;color:#2456D6">Admin</span>'
            if u.is_admin
            else '<span class="pill" style="background:#E9ECF1;color:#6B7280">Usuário</span>'
        )
        trs += f"<tr><td>{u.full_name or '—'}</td><td>{u.email}</td><td>{badge}</td></tr>"
    err_html = '<div class="err">Não foi possível criar (e-mail já existe?).</div>' if erro else ""
    body = f"""<div style="display:flex;align-items:center"><h1 style="margin:0;font-size:20px">Usuários</h1></div>
    {err_html}
    <div class="card" style="padding:0"><table>
      <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th></tr></thead>
      <tbody>{trs}</tbody></table></div>
    <div class="card">
      <h2 style="margin:0 0 12px;font-size:15px">Adicionar usuário</h2>
      <form method="post" action="/app/usuarios" style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:12px;align-items:end">
        <div><label>Nome</label><input name="full_name"></div>
        <div><label>E-mail</label><input name="email" type="email" required></div>
        <div><label>Senha</label><input name="password" type="password" minlength="8" required></div>
        <button class="primary" type="submit">Adicionar</button>
      </form></div>"""
    return HTMLResponse(_shell(tenant, principal, "Usuários", body))


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
