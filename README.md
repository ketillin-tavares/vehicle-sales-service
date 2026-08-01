# vehicle-sales-service

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

## Qualidade

```bash
make quality   # format + lint + typecheck + testes com cobertura
```
