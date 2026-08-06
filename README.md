# vehicle-sales-service

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Quality gate](https://sonarcloud.io/api/project_badges/quality_gate?project=ketillin-tavares_vehicle-sales-service)](https://sonarcloud.io/summary/new_code?id=ketillin-tavares_vehicle-sales-service)

Serviço de venda de veículos: listagem de veículos ordenada por preço, compras e webhook de pagamento.
Possui banco de dados próprio (`vehicle_sales`) e se comunica com o `vehicle-core-service` via HTTP.

## Stack local

| Componente | Porta host | Porta container |
|---|---|---|
| API | 8001 | 8000 |
| PostgreSQL | 5433 | 5432 |
| Floci (emulador AWS) | 4567 | 4566 |

## Como rodar

```bash
cp env.example .env
docker compose up --build
```

Health check: <http://localhost:8001/health>

## Webhook de pagamento

O webhook de pagamento (`POST /webhooks/v1/payments`) é hospedado neste serviço por decisão
deliberada de arquitetura, não por omissão do enunciado: o ciclo de vida da venda e a transição
atômica venda/veículo pertencem ao banco segregado do vehicle-sales-service. Veja a justificativa
completa em [`docs/adr/0001-webhook-pagamento-no-servico-de-vendas.md`](./docs/adr/0001-webhook-pagamento-no-servico-de-vendas.md).

## Qualidade

```bash
make quality   # format + lint + typecheck + testes com cobertura
```

## CI/CD

Definido em `.github/workflows/`:

- **`ci.yml`** — roda em todo Pull Request: `ruff format --check`, `ruff check`, `ty check`,
  `pytest` (unitários com cobertura ≥ 80% + integração via testcontainers), build de imagem Docker
  (smoke test) e, se configurado, análise no SonarCloud.
- **`cd.yml`** — roda a cada push em `main`: repete o quality gate, publica a imagem no Amazon ECR
  e faz o deploy na instância EC2 via AWS Systems Manager (SSM Run Command).
- **`infra.yml`** — execução manual (`workflow_dispatch`) de `terraform apply`/`destroy` da infra
  em produção, protegida pelo ambiente `infra` do GitHub (aprovação obrigatória).

## Infraestrutura e deploy

Detalhes de infraestrutura provisionada, variáveis de ambiente/segredos e deploy em produção estão
documentados separadamente para não duplicar conteúdo:

- [`infra/README.md`](./infra/README.md) — infraestrutura AWS (Terraform Cloud), variáveis de
  ambiente/segredos completas e o fluxo de deploy. Cobre também o provider OIDC do GitHub
  compartilhado com o `vehicle-core-service` e a ordem de apply entre os dois serviços.
- [`infra/local/README.md`](./infra/local/README.md) — como validar a infraestrutura localmente
  com o emulador [Floci](https://hub.docker.com/r/floci/floci).
