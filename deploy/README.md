# Deploy no Swarm via Portainer

Duas stacks, nesta ordem:

| Stack    | Arquivo          | Onde roda     | O quê                         |
|----------|------------------|---------------|-------------------------------|
| `one_db` | `data-stack.yml` | `nettcom-db`  | Postgres 16 (pgvector) + Redis |
| `one`    | `stack.yml`      | `nettcom-app` | migrate + api (x2) + worker    |

Ambas na rede overlay `nettcom` (já existente). O **Nginx Proxy Manager** faz o TLS e o roteamento.

## 0. Pré-requisitos (uma vez)

**No `nettcom-db`** (volumes externos, padrão da casa):
```bash
docker volume create one_pgdata
docker volume create one_redis
```

**Registro privado (GHCR).** A imagem `ghcr.io/nettcomtec/one` é privada. No GitHub,
gere um PAT *classic* com escopo `read:packages` (Settings → Developer settings →
Personal access tokens). No Portainer: **Registries → Add registry → Custom** →
URL `ghcr.io`, usuário `nettcomtec`, senha = o PAT. (Alternativa: tornar o pacote
público em github.com/nettcomtec/one/pkgs/container/one → Package settings.)

**DNS.** Registro `A` wildcard `*.nettcomone.com` → IP do `nettcom-mgr` (onde está o NPM).

**NPM na rede `nettcom`.** O proxy host aponta para `one_api:8000` pelo nome do
serviço, então o container do NPM precisa estar na overlay `nettcom`. Se ainda não
estiver, adicione a rede na stack do NPM (`networks: [nettcom]`) e redeploy.
Alternativa sem mexer no NPM: descomentar o bloco `ports` da `api` no `stack.yml`
(publica `8010` no Swarm) e apontar o proxy host para `http://<ip-do-nettcom-app>:8010`.

## 1. Stack `one_db`

Portainer → Stacks → **Add stack** → nome `one_db` → Web editor → colar `data-stack.yml`.

Environment variables:
```
POSTGRES_PASSWORD = <senha forte>
```
Deploy. Aguarde `postgres` ficar *healthy*.

## 2. Stack `one`

Portainer → Stacks → **Add stack** → nome `one` → colar `stack.yml`.
Em **Registry**, selecione o `ghcr.io` cadastrado.

Environment variables:
```
IMAGE       = ghcr.io/nettcomtec/one:latest
DB_PASSWORD = <a mesma POSTGRES_PASSWORD>
JWT_SECRET  = <openssl rand -hex 32>
BASE_DOMAIN = nettcomone.com
```
Deploy. O serviço `one_migrate` roda uma vez e sai com 0 (é esperado ficar
"complete", não "running"). `one_api` sobe 2 réplicas; `one_worker` 1.

Verificar:
```bash
docker service ls | grep one_
docker service logs one_migrate --tail 20      # deve terminar sem traceback
```

## 2b. Proxy host no Nginx Proxy Manager

**SSL Certificates → Add → Let's Encrypt**: domínios `nettcomone.com` e
`*.nettcomone.com`, marcar **Use a DNS Challenge** (wildcard exige DNS challenge;
escolha o provedor do seu DNS e cole o token da API). Sem DNS challenge, não há
wildcard: crie um proxy host por tenant com certificado HTTP normal.

**Hosts → Proxy Hosts → Add**:

| Campo               | Valor                      |
|---------------------|----------------------------|
| Domain Names        | `*.nettcomone.com`         |
| Scheme              | `http`                     |
| Forward Host / Port | `one_api` / `8000`         |
| Websockets Support  | ligado (futuro realtime)   |
| Block Common Exploits | ligado                   |
| SSL                 | o certificado wildcard, Force SSL, HTTP/2 |

Aba **Advanced** (a API resolve o tenant pelo `Host`, então ele precisa chegar intacto):
```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_read_timeout 120s;
client_max_body_size 50m;
```

Teste: `curl -s https://qualquer.nettcomone.com/healthz` → `{"status":"ok"}`.
(`/healthz` não exige tenant; `/ledger/...` com subdomínio inexistente responde 404 "Unknown tenant" — correto.)

## 3. Primeiro tenant

```bash
docker exec -it $(docker ps -q -f name=one_api | head -1) \
  python -m one.cli create-tenant --name "Nettcom" --slug nettcom

# token de admin para testar a API
docker exec -it $(docker ps -q -f name=one_api | head -1) \
  python -m one.cli issue-token --tenant nettcom --user 00000000-0000-0000-0000-000000000001 --admin
```

`https://nettcom.nettcomone.com/docs` abre o Swagger do tenant.

## 4. Atualizar (git → imagem → Swarm)

Cada push na `main` gera `ghcr.io/nettcomtec/one:latest` e `:sha-<hash>`.
No Portainer: stack `one` → **Update the stack** → marcar *Re-pull image and
redeploy*. O `migrate` roda de novo (idempotente) antes de a `api` trocar de
versão com `start-first` + rollback automático em falha.

Para fixar versão em vez de `latest`, troque `IMAGE` por `ghcr.io/nettcomtec/one:sha-294ad30`.

**Automático (opcional):** Portainer → stack `one` → *Webhook* → copie a URL e
coloque em GitHub → Settings → Secrets → `PORTAINER_WEBHOOK`; depois descomente o
último step do `.github/workflows/ci.yml`. Aí todo push na `main` já faz o deploy.

## Backup

Postgres: `docker exec $(docker ps -q -f name=one_db_postgres) pg_dumpall -U one | gzip > one-$(date +%F).sql.gz`
no `nettcom-db` (cron diário). Cada tenant é um schema, então `pg_dump -n t_<slug>`
exporta/restaura um cliente isoladamente.
