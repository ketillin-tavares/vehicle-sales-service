<!-- Título sugerido: tipo(escopo): resumo curto — ex.: "feat(sale): adiciona filtro de listagem por status" -->

## Descrição

<!-- O que muda e por quê. Referencie a issue/tarefa quando existir. -->

## Tipo de mudança

- [ ] Feature
- [ ] Bugfix
- [ ] Refactor (sem mudança de comportamento)
- [ ] Infra / CI-CD
- [ ] Documentação

## Como foi testado

<!-- Passos objetivos para o revisor validar (rotas chamadas, cenários cobertos, etc.). -->

## Checklist

> Este repositório ainda não tem pipeline de CI configurada em `.github/workflows/` — os checks
> abaixo são de verificação **manual/local** com `make quality` em `service/` antes de abrir o PR.

- [ ] `ruff format --check` e `ruff check` sem apontamentos (`uv run ruff format --check src/ tests/` / `uv run ruff check src/ tests/`)
- [ ] `ty check src/` sem erros de tipagem
- [ ] Testes unitários (`pytest -m "not integration"`) cobrindo o cenário AAA, buscando cobertura ≥ 80% (meta do desafio, ainda sem gate automatizado)
- [ ] Testes de integração (`pytest -m integration`) atualizados/rodados quando a mudança afeta gateways ou infraestrutura
- [ ] Migração Alembic criada e testada, se o schema do banco mudou
- [ ] Sem segredos, `.env` ou credenciais no diff
- [ ] Clean Architecture respeitada (domínio sem dependência de application/interface/infrastructure)
- [ ] Docs atualizadas quando aplicável (`README.md`, ADRs em `docs/adr/`)
