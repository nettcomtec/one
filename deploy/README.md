# Deploy no Swarm via Portainer

Duas stacks, nesta ordem:

| Stack    | Arquivo          | O quê                         |
|----------|------------------|-------------------------------|
| `one_db` | `data-stack.yml` | Postgres 16 (pgvector) + Redis |
| `one`    | `stack.yml`      | migrate + api (x2) + worker    |

Ambas na rede overlay `nettcom` (já existente). O **Nginx Proxy Manager** faz o TLS e o roteamento.

## 0. Pré-requisitos (uma vez)

**Volumes:** criados automaticamente pelo Swarm no deploy (`one_db_one_pgdata`,
`one_db_one_redis`). Nada a pré-criar. As stacks não fixam nó (sem `placement`);
num cluster multi-nó, adicione `placement.constraints` conforme o seu layout.

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

Environment variables (aba **Environment variables**, botão *+ Add an environment variable*,
uma por linha — `IMAGE` e `BASE_DOMAIN` já têm padrão na stack, só sobrescreva se quiser):
```
DB_PASSWORD = <a mesma POSTGRES_PASSWORD>
JWT_SECRET  = <openssl rand -hex 32>
IMAGE       = ghcr.io/nettcomtec/one:latest      (opcional; padrão)
BASE_DOMAIN = nettcomone.com                     (opcional; padrão)
```
> Erro `invalid image reference for service api: no image specified` = a variável
> `IMAGE` chegou vazia. Com o padrão `${IMAGE:-…}` na stack isso não ocorre mais; se
> for sobrescrever, confira que o nome é exatamente `IMAGE`, sem `$` e sem aspas.
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

## 4. Autodeploy (git → imagem → Swarm, sem tocar no Portainer)

Objetivo: depois do setup abaixo, **todo `git push` na `main`** builda a imagem
e redeploya sozinho. No Swarm não existe "webhook de stack" — o que existe é
**webhook por serviço**. Setup único:

1. **Webhook do serviço `one_api`.** Portainer → **Services** → clique em `one_api`
   → seção **Service webhook** → ative → copie a URL
   (`https://<portainer>/api/webhooks/<uuid>`). Repita em `one_worker`.
2. **Secret no GitHub.** Repo `nettcomtec/one` → Settings → Secrets and variables →
   Actions → *New repository secret* → nome `PORTAINER_WEBHOOK`, valor = as duas URLs
   (uma por linha, ou separadas por vírgula).
3. **Credencial do GHCR p/ o redeploy.** O webhook re-puxa a imagem, então o
   Portainer precisa baixá-la: torne o pacote público
   (github.com/nettcomtec/one/pkgs/container/one → *Package settings* → *Public*),
   ou Portainer → Registries → *Add registry* → `ghcr.io` + PAT `read:packages`.

Pronto. O passo "Redeploy no Swarm via Portainer" no `.github/workflows/ci.yml`
dispara os webhooks em cada push na `main` (e fica inerte enquanto o secret não
existir). Cada serviço re-puxa `:latest` e troca com `start-first` + rollback. A API
roda as migrações no boot (advisory lock), então não há serviço `migrate` a orquestrar.

**Manual, se precisar** (sem webhook): no servidor,
`docker service update --with-registry-auth --image ghcr.io/nettcomtec/one:latest --force one_api`
(idem `one_worker` e `one_migrate`); ou Portainer → stack `one` → *Update the stack*
com *Re-pull image*. Para fixar versão, troque `IMAGE` por `:sha-<hash>`.

## Backup

Postgres: `docker exec $(docker ps -q -f name=one_db_postgres) pg_dumpall -U one | gzip > one-$(date +%F).sql.gz`
no `nettcom-db` (cron diário). Cada tenant é um schema, então `pg_dump -n t_<slug>`
exporta/restaura um cliente isoladamente.
