# Migrations

Fase 0 cria o schema via metadata do SQLAlchemy (`python -m one.db.migrate`),
que é determinístico e suficiente enquanto os modelos ainda mudam muito.

Quando os modelos estabilizarem e começarmos a evoluir schema em produção,
Alembic entra aqui com duas environments:

- `migrations/` — schema `public` (registro de tenants).
- `tenant_migrations/` — aplicado a cada schema `t_<slug>` com
  `version_table_schema` próprio, iterando os tenants no deploy.

Até lá, estes diretórios ficam reservados.
