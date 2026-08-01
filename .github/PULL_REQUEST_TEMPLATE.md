# Descricao

<!-- O que muda e por que. Referencie a issue/tarefa quando existir. -->

## Tipo de mudanca

- [ ] Feature
- [ ] Bugfix
- [ ] Refactor (sem mudanca de comportamento)
- [ ] Infra / CI-CD
- [ ] Documentacao

## Servicos afetados

- [ ] `services/core`
- [ ] `services/sales`
- [ ] `infra/` ou `.github/workflows/`

## Checklist

- [ ] `make ci` passou localmente nos servicos afetados
- [ ] Testes novos/atualizados cobrem a mudanca (padrao AAA)
- [ ] Sem segredos, `.env` ou credenciais no diff
- [ ] Clean Architecture respeitada (dominio sem dependencias de infra)
- [ ] Docs/README atualizados quando aplicavel

## Como testar

<!-- Passos objetivos para o revisor validar. -->
