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

Itens abaixo são os mesmos verificados pela pipeline (`.github/workflows/ci.yml`) — rode
`make quality` em `service/` antes de abrir o PR para confirmar tudo de uma vez:

- [ ] `ruff format --check` e `ruff check` sem apontamentos (`uv run ruff format --check src/ tests/` / `uv run ruff check src/ tests/`)
- [ ] `ty check src/` sem erros de tipagem
- [ ] Testes unitários (`pytest -m "not integration"`) cobrindo o cenário AAA, com cobertura ≥ 80% (gate da CI: `--cov-fail-under=80`)
- [ ] Testes de integração (`pytest -m integration`) atualizados/rodados quando a mudança afeta gateways ou infraestrutura
- [ ] Migração Alembic criada e testada, se o schema do banco mudou
- [ ] Sem segredos, `.env` ou credenciais no diff
- [ ] Clean Architecture respeitada (domínio sem dependência de application/interface/infrastructure)
- [ ] Quality Gate do SonarCloud verde (`sonar.qualitygate.wait=true` — reprovar aqui **bloqueia o deploy**)
- [ ] Docs atualizadas quando aplicável (`README.md`, `infra/README.md`, `infra/local/README.md`, ADRs em `docs/adr/`)

## Se o PR toca `infra/`

<!-- Ignore esta seção se o diff não tem nada em infra/. -->

- [ ] `terraform fmt -check -recursive infra/` e `terraform validate` limpos em `infra/main` e `infra/local`
- [ ] **Recurso ou argumento novo em `infra/stack/`? A `tfc-run-role-policy.json` foi revisada recurso-a-recurso** (create, plan/refresh, update **e destroy**). A policy é o único artefato que nenhuma validação local exercita: `plan` não a testa e o Floci autoriza qualquer chamada porque não implementa autorização IAM. Ela só falha no meio do `apply`
- [ ] **Removeu alguma permissão?** Excesso falha para o lado seguro; remoção falha no apply — ver o caso do `pg:*` em [`infra/README.md`](../infra/README.md)
- [ ] **`tfc-run-role-policy.json` mudou? Re-cole o JSON na inline policy da role no console AWS.** A policy não acompanha o git — o arquivo só chega à AWS quando você o cola de novo
- [ ] `create_github_oidc_provider` continua `false` — o provider OIDC é compartilhado e pertence ao `vehicle-core-service`, que precisa estar aplicado **antes** desta stack

## Se o PR toca segredos ou configuração compartilhada

- [ ] `INTERNAL_API_TOKEN` continua **byte a byte idêntico** ao do `vehicle-core-service` (divergência = 401 em toda chamada interna)
- [ ] Segredo novo? Vai para o SSM como `SecureString` e é passado ao container **pelo ambiente do processo**, nunca escrito no `.env` — o Compose interpola `${...}` em valores de `env_file`, e o `alembic/env.py` monta o `Settings` inteiro no import, então o container de migrations também precisa recebê-lo

> **Atenção:** merge em `main` dispara deploy automático em produção (`cd.yml`: build da imagem,
> push para o ECR e rollout na EC2 via SSM). Confirme que os itens acima passaram antes de
> aprovar/mergear.
>
> O `cd.yml` só dispara quando o merge toca `service/**`, `deploy/**` ou o próprio `cd.yml` —
> mudanças exclusivamente de infra ou de documentação **não** fazem deploy. Alteração de infra é
> aplicada rodando o `infra.yml` manualmente.
