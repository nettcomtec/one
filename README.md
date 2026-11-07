# Nettcom ONE — ERP AI-native, multi-tenant

Fundação (Fase 0) de um ERP all-in-one para substituir o Odoo, construído para
rodar no Docker Swarm da Nettcom. **Não usa Supabase** — Postgres puro + Redis.
A lógica de negócio vive no backend (FastAPI), não em RLS/Edge Functions.

## Decisões de arquitetura

| Tema          | Escolha                                                                 |
|---------------|-------------------------------------------------------------------------|
| Backend       | Python 3.12 + FastAPI (monólito modular)                                 |
| Dados         | **Postgres puro** self-hosted (sem stack Supabase)                       |
| Multi-tenant  | **Schema por cliente** (`t_<slug>`), isolado via `search_path`          |
| Auth          | Própria, no módulo `identity` (JWT) — sem GoTrue                         |
| Fila/eventos  | Redis + arq; event bus in-process plugável                              |
| Storage       | MinIO/S3 (quando chegarem os anexos) — fora da stack Supabase            |
| IA            | Tool registry tipado (padrão MCP): agente opera o ERP pelas mesmas ações |
| Fiscal        | Camada `FiscalProvider` — cálculo é nosso, emissão/SPED via provedor     |

## Como implementamos: uma stack, git gerando imagem

- **Monorepo único.** A CI (`.github/workflows/ci.yml`) roda testes e builda
  **uma imagem** (multi-stage `Dockerfile`), empurrada pro registry (GHCR)
  taggeada por `sha` + semver.
- **A mesma imagem tem 3 papéis**, selecionados por `ONE_ROLE`
  (`docker-entrypoint.sh`): `api` (uvicorn), `worker` (arq), `migrate`
  (aplica o schema em todos os tenants). Um artefato, três papéis (12-factor).
- **Deploy no Swarm** por `deploy/stack.yml` (Portainer/GitOps): `migrate` roda
  uma vez por deploy, `api` sobe atrás do Traefik roteado por subdomínio
  (`<slug>.nettcomone.com` → resolve o tenant), `worker` processa jobs.
- **Dados em stack separada** (Postgres + Redis), compartilhada entre tenants.

## Estrutura

```
src/one/
  config.py            # settings 12-factor (ONE_*)
  db/                  # base/metadata, engine, sessão por tenant, migrate
  tenancy/             # registro de tenants (public), contexto, middleware, provisioning
  identity/            # usuários, papéis, permissões (RBAC) + JWT
  ledger/              # partida dobrada: Account/Journal/Move/MoveLine + service + tools
  sequences/           # numeração atômica (FOR UPDATE) p/ docs fiscais
  ai/                  # registry de ferramentas (MCP-like) + event bus
  jobs/                # worker arq
  api/                 # routers (health, ledger, ai) + deps (sessão/tenant/perm)
```

## Rodando local

```bash
pip install -e ".[dev]"
docker compose up -d db redis
python -m one.cli migrate                                   # cria public
python -m one.cli create-tenant --name "Cliente X" --slug cliente_x
ONE_ROLE=api uvicorn one.main:app --reload
# token de dev:
python -m one.cli issue-token --tenant cliente_x --user 00000000-0000-0000-0000-000000000001 --admin
pytest -q
```

Chamada de exemplo (o agente de IA usa o mesmo caminho via `/ai/execute`):

```bash
curl -X POST localhost:8000/ledger/moves \
  -H "X-Tenant: cliente_x" -H "Authorization: Bearer <token>" \
  -d '{"journal_id":"<uuid>","lines":[
        {"account_id":"<uuid>","debit":"100.00"},
        {"account_id":"<uuid>","credit":"100.00"}]}'
```

## Roadmap (ordem de dependência)

0. **Fundação** ← *este scaffold* (tenancy, RBAC, ledger, sequências, IA, jobs)
1. CRM + Agenda + Help Desk + WhatsApp + VoIP
2. Vendas + Contratos + Serviços recorrentes
3. Fiscal (provedor) + Financeiro
4. Inventário + PDV
5. Projetos + RH + Marketing/Social/Campanhas
6. Fabricação + Qualidade
