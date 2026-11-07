"""Presentation layer — CSS, icons and HTML builders shared by the web routes.

Pure functions over plain data (no DB, no request), so the same templates render
the live pages and an offline preview. Design: Inter, deep-ink sidebar, single
blue accent, hairline cards with soft shadows; dense but calm.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- tokens + css
CSS = """
:root{
  --ink:#0E1626; --ink-2:#17203380; --side-idle:#9AA4B8; --side-hover:#C7D0E0;
  --bg:#F6F7F9; --card:#FFFFFF; --line:#ECEEF2; --line-2:#F2F4F7;
  --fg:#101828; --fg-2:#667085; --fg-3:#98A2B3;
  --acc:#2456D6; --acc-700:#1B44AD; --acc-100:#EAF0FE; --acc-soft:#7AA2F7;
  --ok:#027A48; --ok-bg:#ECFDF3; --warn:#B54708; --warn-bg:#FFFAEB;
  --dan:#B42318; --dan-bg:#FEF3F2; --dan-line:#FECDCA;
  --r-card:14px; --r-ctl:10px; --r-pill:8px;
  --sh:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.06);
  --sh-md:0 4px 12px rgba(16,24,40,.08),0 2px 4px rgba(16,24,40,.04);
}
*{box-sizing:border-box}
html,body{margin:0}
body{font-family:Inter,system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);
  font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--acc);text-decoration:none}a:hover{color:var(--acc-700)}
h1,h2,h3{margin:0;letter-spacing:-.018em;font-weight:600}
svg{display:block}

/* layout */
.wrap{display:flex;flex-wrap:wrap;min-height:100vh}
nav.side{width:244px;flex:0 0 244px;background:var(--ink);color:var(--side-idle);
  display:flex;flex-direction:column;padding:14px 12px;gap:2px;min-height:100vh;position:sticky;top:0;align-self:flex-start}
.brand{display:flex;align-items:center;gap:11px;padding:8px 8px 16px}
.logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#2E5BE0,#1E49C7);
  display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:15px;box-shadow:0 2px 6px rgba(36,86,214,.4)}
.brand b{color:#fff;font-weight:600;font-size:14.5px;display:block;line-height:1.2}
.brand span{font-size:11.5px;color:#64708A}
.navlabel{font-size:10.5px;font-weight:600;letter-spacing:.07em;color:#55617A;text-transform:uppercase;padding:14px 10px 6px}
nav.side a.item{display:flex;align-items:center;gap:11px;padding:8.5px 10px;border-radius:var(--r-pill);
  color:var(--side-idle);font-size:13.5px;font-weight:450;transition:background .12s,color .12s}
nav.side a.item:hover{background:#17213A;color:var(--side-hover)}
nav.side a.item svg{width:18px;height:18px;stroke:currentColor;opacity:.85}
nav.side a.item.on{background:#1B2946;color:#fff;font-weight:550}
nav.side a.item.on svg{stroke:var(--acc-soft);opacity:1}
.side-foot{margin-top:auto;border-top:1px solid #1C2740;padding-top:10px;display:flex;align-items:center;gap:10px;padding-left:8px}
.avatar{width:30px;height:30px;border-radius:50%;background:#2B3A5C;color:#fff;display:flex;align-items:center;
  justify-content:center;font-size:11.5px;font-weight:600;flex:0 0 30px}
.side-foot b{color:#fff;font-size:13px;font-weight:500;display:block;line-height:1.3}
.side-foot a{font-size:11.5px;color:#64708A}.side-foot a:hover{color:var(--side-hover)}

main{flex:999 1 560px;min-width:0;display:flex;flex-direction:column}
header.top{height:60px;background:var(--card);border-bottom:1px solid var(--line);display:flex;
  align-items:center;gap:14px;padding:0 24px;position:sticky;top:0;z-index:5}
.crumb{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg-2)}
.crumb .sep{color:var(--fg-3)}.crumb b{color:var(--fg);font-weight:600}
.search{position:relative;flex:1;max-width:440px}
.search svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:16px;height:16px;stroke:var(--fg-3)}
.search input{width:100%;height:38px;border:1px solid var(--line);border-radius:var(--r-ctl);
  padding:0 12px 0 36px;font:inherit;font-size:13px;background:#FBFCFD;color:var(--fg)}
.iconbtn{width:38px;height:38px;border-radius:var(--r-ctl);border:1px solid var(--line);background:var(--card);
  display:flex;align-items:center;justify-content:center;cursor:pointer}
.iconbtn svg{width:18px;height:18px;stroke:var(--fg-2)}
.iconbtn:hover{background:var(--bg)}

.content{padding:26px 28px;display:flex;flex-direction:column;gap:22px;max-width:1180px;width:100%}
.page-h{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap}
.page-h h1{font-size:22px}.page-h .sub{color:var(--fg-2);font-size:13.5px;margin-top:3px}
.spacer{flex:1}

/* cards */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r-card);box-shadow:var(--sh)}
.card.pad{padding:20px}
.grid-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
.kpi{padding:18px 18px 16px;display:flex;flex-direction:column;gap:7px}
.kpi .l{font-size:12px;color:var(--fg-2);font-weight:500;display:flex;align-items:center;gap:7px}
.kpi .l .dot{width:8px;height:8px;border-radius:50%}
.kpi .n{font-size:27px;font-weight:650;letter-spacing:-.03em;line-height:1}
.kpi .d{font-size:12px;font-weight:500}
.d.up{color:var(--ok)}.d.down{color:var(--dan)}.d.mut{color:var(--fg-3)}

.banner{display:flex;gap:14px;align-items:flex-start;padding:18px 20px}
.banner .ic{width:38px;height:38px;border-radius:10px;background:var(--acc-100);display:flex;align-items:center;justify-content:center;flex:0 0 38px}
.banner .ic svg{width:20px;height:20px;stroke:var(--acc)}
.banner h2{font-size:15.5px;margin-bottom:3px}
.banner p{margin:0;color:var(--fg-2);font-size:13.5px;line-height:1.55}

/* table */
table{width:100%;border-collapse:collapse;font-size:13.5px}
thead th{text-align:left;color:var(--fg-2);font-size:11.5px;font-weight:600;letter-spacing:.03em;
  text-transform:uppercase;padding:12px 16px;background:var(--line-2);border-bottom:1px solid var(--line)}
tbody td{padding:13px 16px;border-top:1px solid var(--line-2)}
tbody tr:first-child td{border-top:0}
tbody tr:hover{background:#FCFCFD}
.u-name{display:flex;align-items:center;gap:10px;font-weight:500}
.u-av{width:30px;height:30px;border-radius:50%;background:var(--acc-100);color:var(--acc);display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:600;flex:0 0 30px}
.pill{font-size:11px;border-radius:999px;padding:2.5px 9px;font-weight:600;display:inline-flex;align-items:center;gap:5px}
.pill.blue{background:var(--acc-100);color:var(--acc)}
.pill.gray{background:#F2F4F7;color:var(--fg-2)}
.pill.green{background:var(--ok-bg);color:var(--ok)}

/* forms */
label{font-size:12.5px;color:var(--fg-2);font-weight:500;display:block;margin-bottom:6px}
input[type=text],input[type=email],input[type=password]{height:40px;border:1px solid var(--line);
  border-radius:var(--r-ctl);padding:0 12px;font:inherit;font-size:14px;width:100%;color:var(--fg);background:var(--card);
  transition:border-color .12s,box-shadow .12s}
input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(36,86,214,.12)}
.btn{height:40px;border:0;border-radius:var(--r-ctl);background:var(--acc);color:#fff;font:inherit;font-size:14px;
  font-weight:600;padding:0 18px;cursor:pointer;box-shadow:0 1px 2px rgba(16,24,40,.12);transition:background .12s,transform .05s}
.btn:hover{background:var(--acc-700)}.btn:active{transform:translateY(1px)}
.btn.block{width:100%;height:44px}
.form-row{display:flex;flex-direction:column;gap:14px}
.err{background:var(--dan-bg);color:var(--dan);border:1px solid var(--dan-line);border-radius:var(--r-ctl);
  padding:10px 13px;font-size:13.5px;display:flex;align-items:center;gap:9px}
.err svg{width:16px;height:16px;stroke:var(--dan);flex:0 0 16px}
.card-head{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px}
.card-head h2{font-size:15px}

/* auth */
.auth-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
  background:radial-gradient(1200px 420px at 50% -8%,#EEF2FB 0,var(--bg) 60%)}
.auth{width:100%;max-width:392px;display:flex;flex-direction:column;gap:20px}
.auth-brand{display:flex;align-items:center;gap:11px;justify-content:center}
.auth-brand b{font-weight:650;font-size:17px;letter-spacing:-.02em}
.auth .card{padding:26px 24px;display:flex;flex-direction:column;gap:18px;box-shadow:var(--sh-md)}
.auth h1{font-size:19px}.auth .lead{color:var(--fg-2);font-size:13.5px;margin-top:4px}
.auth .foot{text-align:center;color:var(--fg-3);font-size:12.5px}

@media(max-width:720px){
  nav.side{width:100%;flex-basis:100%;min-height:0;position:static;flex-direction:row;flex-wrap:wrap;overflow:auto}
  .brand{width:100%}.navlabel{display:none}.side-foot{margin:0}
  .content{padding:18px 16px}
}
"""

_ICONS = {
    "home": '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "crm": '<path d="M16 21v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-1a4 4 0 0 0-3-3.87"/>',
    "chat": '<path d="M4 4h16v12H8l-4 4z"/>',
    "ticket": '<path d="M4 9a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2 2 2 0 0 0 0 6 2 2 0 0 1-2 2H6a2 2 0 0 1-2-2 2 2 0 0 0 0-6z"/><path d="M13 7v10" stroke-dasharray="1 3"/>',
    "cart": '<path d="M4 5h2l2.4 11.2a1 1 0 0 0 1 .8h7.7a1 1 0 0 0 1-.8L21 8H7"/><circle cx="10" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
    "coin": '<path d="M12 3v18M7 7h7a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h8"/>',
    "doc": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "box": '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    "project": '<path d="M4 5h16v14H4z"/><path d="M4 10h16M9 5v14"/>',
    "people": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4.9a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.5a7 7 0 0 0-2 1.2L5 5.8 3 9.3l2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-.9a7 7 0 0 0 2 1.2L10 21h4l.5-2.5a7 7 0 0 0 2-1.2l2.4.9 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    "spark": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    "warn": '<path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
}


def icon(name: str, cls: str = "") -> str:
    body = _ICONS.get(name, "")
    c = f' class="{cls}"' if cls else ""
    return (
        f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


# navigation: (href, label, icon, is_active_key)
NAV = [
    ("/app", "Início", "home"),
    ("/app", "CRM", "crm"),
    ("/app", "Atendimento", "chat"),
    ("/app", "Vendas", "cart"),
    ("/app", "Financeiro", "coin"),
    ("/app", "Fiscal", "doc"),
    ("/app/usuarios", "Usuários", "people"),
]

_HEAD = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700&display=swap" rel="stylesheet">
<style>{css}</style></head><body>"""


def _head(title: str) -> str:
    return _HEAD.format(title=title, css=CSS)


def shell(*, tenant_slug: str, user_email: str, active: str, body: str) -> str:
    items = ""
    for href, label, ic in NAV:
        on = " on" if label == active else ""
        items += f'<a class="item{on}" href="{href}">{icon(ic)}<span>{label}</span></a>'
    initials = (user_email or "?")[:2].upper()
    return f"""{_head("Nettcom ONE")}
<div class="wrap">
  <nav class="side">
    <div class="brand"><div class="logo">N</div><div><b>Nettcom ONE</b><span>{tenant_slug}</span></div></div>
    <div class="navlabel">Workspace</div>
    {items}
    <div class="side-foot">
      <div class="avatar">{initials}</div>
      <div style="flex:1;min-width:0"><b style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{user_email}</b>
        <a href="/logout">Sair</a></div>
      <a class="iconbtn" href="/app" style="width:30px;height:30px;border-color:#20304F;background:transparent">{icon("settings")}</a>
    </div>
  </nav>
  <main>
    <header class="top">
      <div class="crumb"><span>{active}</span></div>
      <div class="search">{icon("search")}<input type="search" placeholder="Buscar ou pedir ao agente…  (Ctrl K)" aria-label="Buscar"></div>
      <div class="spacer"></div>
      <button class="iconbtn" aria-label="Notificações">{icon("bell")}</button>
    </header>
    <div class="content">{body}</div>
  </main>
</div></body></html>"""


def auth_page(title: str, inner: str) -> str:
    return f"""{_head(title + " · Nettcom ONE")}
<div class="auth-wrap"><div class="auth">
  <div class="auth-brand"><div class="logo">N</div><b>Nettcom ONE</b></div>
  {inner}
  <div class="foot">Plataforma de gestão · Nettcom Tecnologia</div>
</div></div></body></html>"""


# --------------------------------------------------------------------------- page bodies
def dashboard_body(*, tenant_slug: str, users: int) -> str:
    return f"""
    <div class="page-h"><div><h1>Bem-vindo de volta</h1>
      <div class="sub">Workspace <b style="color:var(--fg)">{tenant_slug}</b> · você é administrador</div></div></div>
    <div class="grid-kpi">
      <div class="card kpi"><div class="l"><span class="dot" style="background:var(--acc)"></span>Usuários</div>
        <div class="n">{users}</div><div class="d mut">ativos no workspace</div></div>
      <div class="card kpi"><div class="l"><span class="dot" style="background:#9B8AFB"></span>Oportunidades</div>
        <div class="n">0</div><div class="d mut">pipeline vazio</div></div>
      <div class="card kpi"><div class="l"><span class="dot" style="background:#F79009"></span>Tickets abertos</div>
        <div class="n">0</div><div class="d mut">nenhum pendente</div></div>
      <div class="card kpi"><div class="l"><span class="dot" style="background:var(--ok)"></span>A receber</div>
        <div class="n">R$ 0</div><div class="d mut">próximos 30 dias</div></div>
    </div>
    <div class="card banner">
      <div class="ic">{icon("spark")}</div>
      <div><h2>Está no ar 🎉</h2>
        <p>Login, multi-tenant e o shell do app funcionando. Os módulos — CRM, Vendas, Financeiro, Fiscal — entram a seguir,
        cada um já herdando permissões, auditoria e o agente de IA que trabalha dentro do sistema.
        Enquanto isso, você pode gerenciar <a href="/app/usuarios">usuários</a> ou abrir a <a href="/docs">API</a>.</p></div>
    </div>"""


def users_body(*, users: list[dict], error: bool) -> str:
    rows = ""
    for u in users:
        av = (u["email"] or "?")[:2].upper()
        badge = (
            '<span class="pill blue">Admin</span>'
            if u["is_admin"]
            else '<span class="pill gray">Usuário</span>'
        )
        rows += (
            f'<tr><td><div class="u-name"><span class="u-av">{av}</span>{u["name"] or "—"}</div></td>'
            f'<td style="color:var(--fg-2)">{u["email"]}</td><td>{badge}</td></tr>'
        )
    err = f'<div class="err">{icon("warn")}Não foi possível criar (e-mail já existe?).</div>' if error else ""
    return f"""
    <div class="page-h"><div><h1>Usuários</h1><div class="sub">{len(users)} no workspace</div></div></div>
    {err}
    <div class="card"><table>
      <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <div class="card">
      <div class="card-head"><h2>Adicionar usuário</h2></div>
      <form method="post" action="/app/usuarios" style="padding:18px 20px;display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:14px;align-items:end">
        <div><label>Nome</label><input type="text" name="full_name" placeholder="Nome completo"></div>
        <div><label>E-mail</label><input type="email" name="email" required placeholder="[email protected]"></div>
        <div><label>Senha</label><input type="password" name="password" minlength="8" required placeholder="mín. 8 caracteres"></div>
        <button class="btn" type="submit">Adicionar</button>
      </form></div>"""


def setup_body(*, tenant_slug: str) -> str:
    return f"""<div class="card">
    <div><h1>Criar superusuário</h1><div class="lead">Primeiro acesso do workspace <b style="color:var(--fg)">{tenant_slug}</b>.</div></div>
    <form method="post" action="/setup" class="form-row">
      <div><label>Nome</label><input type="text" name="full_name" required autofocus placeholder="Seu nome"></div>
      <div><label>E-mail</label><input type="email" name="email" required placeholder="[email protected]"></div>
      <div><label>Senha</label><input type="password" name="password" minlength="8" required placeholder="mín. 8 caracteres"></div>
      <button class="btn block" type="submit">Criar e entrar</button>
    </form></div>"""


def login_body(*, error: bool) -> str:
    err = f'<div class="err">{icon("warn")}E-mail ou senha inválidos.</div>' if error else ""
    return f"""<div class="card">
    <h1>Entrar</h1>
    {err}
    <form method="post" action="/login" class="form-row">
      <div><label>E-mail</label><input type="email" name="email" required autofocus placeholder="[email protected]"></div>
      <div><label>Senha</label><input type="password" name="password" required placeholder="Sua senha"></div>
      <button class="btn block" type="submit">Entrar</button>
    </form></div>"""
