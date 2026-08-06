# Infraestrutura local (Floci) — vehicle-sales-service

Como validar a stack Terraform de infraestrutura (`infra/stack`) localmente, **sem tocar a AWS
real**, usando o emulador [Floci](https://hub.docker.com/r/floci/floci). Este README cobre apenas a
validação da infraestrutura; para rodar a aplicação localmente veja o
[README raiz](../../README.md), e para o significado de cada recurso provisionado e o deploy em
produção veja [`infra/README.md`](../README.md).

## O que é esta raiz

`infra/local/` é uma raiz Terraform separada de `infra/main/` (produção), mas que reutiliza o
**mesmo módulo** `infra/stack/` — nenhum recurso é reescrito para a emulação. As únicas diferenças
em relação a produção são variáveis do módulo:

- `aws_endpoint_url = "http://localhost:4566"` — aponta o provider AWS para o Floci em vez da AWS
  real.
- `enable_github_oidc = false` — o Floci não implementa nem `CreateOpenIDConnectProvider` nem
  `GetOpenIDConnectProvider`; esta raiz desliga tanto a criação quanto a **leitura** do provider
  compartilhado (a data source que, em produção, lê o provider do `vehicle-core-service`), além da
  role de deploy. É a flag `enable_github_oidc`, não `create_github_oidc_provider`: em produção esta
  stack já usa `create_github_oidc_provider = false` (ela lê, nunca cria, o provider — quem cria é o
  Core), então zerar só `create_github_oidc_provider` aqui não bastaria — a data source ainda tentaria
  chamar `GetOpenIDConnectProvider`, que o Floci também não suporta. Ver o detalhamento das duas
  flags em [`infra/README.md`](../README.md#o-provider-oidc-é-um-recurso-compartilhado-e-o-core-é-dono-dele).
- Backend **local** (sem `cloud {}`), state descartável — nunca é uma fonte de verdade.
- `github_repository_id = "0"` — valor qualquer: a variável não tem default no módulo (ver
  [`infra/README.md`](../README.md#github_repository_id-não-tem-default-de-propósito)), mas com
  `enable_github_oidc = false` nada a lê de verdade nesta raiz.

Tudo o mais (EC2, Security Groups, Elastic IP, RDS com senha gerenciada em Secrets Manager, ECR, IAM
roles/instance profile incluindo a policy `Deny` do prefixo SSM do serviço par, KMS CMK, parâmetros
SSM) é aplicado de verdade contra o emulador.

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) (o Floci precisa do socket do Docker do host para
  emular EC2/RDS com containers reais)
- [Terraform](https://developer.hashicorp.com/terraform/downloads) `>= 1.6.0`
- Bash (o script `floci-validate.sh` é um script shell)

## Como rodar

O script `floci-validate.sh` cuida de subir o Floci (se ainda não estiver rodando), rodar o
Terraform e limpar tudo ao final:

```bash
cd infra/local
./floci-validate.sh          # terraform fmt -check + init + validate + plan
./floci-validate.sh --apply  # o mesmo, + apply completo + terraform state list + destroy
```

O script:

1. Roda `terraform fmt -check -recursive` na árvore de `infra/`.
2. Verifica se algo já está escutando em `:4566`; se não, sobe o container
   `floci/floci:latest` publicando a porta `4566` **com o socket do Docker do host montado**
   (`-v /var/run/docker.sock:/var/run/docker.sock` — obrigatório: sem ele, instâncias EC2 vão para
   `pending → terminated` e chamadas ao RDS falham com `SocketException`).
3. Usa credenciais AWS fictícias (`AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`,
   `AWS_DEFAULT_REGION=us-east-1`) — o Floci não as valida.
4. Roda `terraform init` (backend local) + `validate` + `plan`.
5. Com `--apply`: roda `terraform apply -auto-approve`, lista os recursos criados
   (`terraform state list`) e em seguida `terraform destroy -auto-approve`.
6. Ao sair (sucesso ou erro), remove `terraform.tfstate`/`terraform.tfstate.backup` locais, para o
   container do Floci (se foi este script que o iniciou) e remove, best-effort, quaisquer
   containers residuais criados pelo Floci para emular EC2/RDS/ECR
   (`floci-ec2-*`, `floci-rds-*`, `floci-ecr-*`).

> **Importante:** a imagem correta é sempre `floci/floci:latest` — **nunca** `latest-compat`.

## Variáveis de ambiente

Não há `.env` nesta raiz: as credenciais fictícias são exportadas pelo próprio
`floci-validate.sh`. A única configuração é feita via variáveis do módulo Terraform, já fixadas em
`infra/local/main.tf`:

| Variável do módulo | Valor local | Equivalente em produção |
|---|---|---|
| `aws_region` | `us-east-1` | `us-east-1` (padrão, configurável) |
| `github_org` | `floci-local` | organização/usuário real do GitHub (`github_org` do workspace) |
| `aws_endpoint_url` | `http://localhost:4566` | `null` (usa a AWS real) |
| `enable_github_oidc` | `false` | `true` (padrão) |
| `github_repository_id` | `"0"` (não lido — `enable_github_oidc = false`) | id numérico real do repositório, sem default (workspace) |

## O Floci não valida autorização IAM

> ⚠️ **Este é o caveat central de qualquer validação local nesta plataforma — leia antes de confiar
> num `floci-validate.sh --apply` verde.**

O emulador aceita **qualquer** credencial e autoriza **toda** chamada — ele não implementa o motor
de autorização do IAM. Consequência prática: falhas de `AccessDenied` são **estruturalmente
invisíveis** na validação local. Um `floci-validate.sh` verde prova apenas que o grafo de recursos e
o formato dos argumentos estão corretos; **não prova absolutamente nada sobre permissões**. O único
artefato desta stack que nenhum run local consegue validar é justamente a `tfc-run-role-policy.json`
— a policy de menor privilégio escrita à mão que a run role real da TFC usa contra a AWS de verdade.
Toda mudança em `infra/stack/` exige uma revisão manual casada dessa policy; o `plan` local não
avisa, porque o Floci não consulta o IAM. O único teste real da run role é um `apply`/`destroy`
contra a AWS de verdade — mesma lição documentada em
`vehicle-core-service/infra/local/README.md`, onde esse ponto cego já causou retrabalho real neste
projeto.

## Diferenças conhecidas em relação à AWS real

| Achado | Tratamento |
|---|---|
| O Floci sustenta instâncias EC2 e bancos RDS com containers Docker reais, usando o socket do host | `floci-validate.sh` sobe o Floci com o socket montado — **obrigatório**; sem isso o EC2 vai para `pending→terminated` e o RDS falha com `SocketException` |
| Nem `CreateOpenIDConnectProvider` nem `GetOpenIDConnectProvider` são suportados | `enable_github_oidc = false` é definido **somente** em `infra/local` — pula o recurso, a data source do provider compartilhado e a role de deploy apenas localmente |
| Não há como emular a leitura do provider OIDC criado pela stack do Core (sequer existe localmente) | Esta raiz nunca lê ou depende do Core; a ordem "Core primeiro" documentada em `infra/README.md` só se aplica à AWS real |
| Todo o resto (EC2, SG, EIP, RDS incluindo master password gerenciada/Secrets Manager, ECR + política de ciclo de vida, roles/instance profiles/políticas IAM incluindo o `Deny` do prefixo SSM do serviço par, KMS CMK + alias + rotação + SSM `SecureString` via CMK, parâmetros SSM, data sources de VPC default e AMI AL2023) | Aplicado de verdade contra o emulador — `apply`/`destroy` completos no script |

## Fluxo recomendado

1. Após qualquer alteração em `infra/stack/`, rode `./floci-validate.sh --apply` localmente antes
   de abrir o Pull Request — valida `fmt`, `plan` e um ciclo completo de `apply`/`destroy` sem custo
   e sem risco para a conta AWS real.
2. Revise manualmente `infra/tfc-run-role-policy.json` contra o que mudou em `infra/stack/` — o
   Floci não faz essa checagem por você (ver acima).
3. Só depois disso, o workflow `infra.yml` (`workflow_dispatch`, ambiente `infra` no GitHub) aplica
   a mesma mudança em produção via `infra/main`, contra a AWS real através da Terraform Cloud —
   **desde que a infraestrutura do `vehicle-core-service` já esteja aplicada** (ver
   [`infra/README.md`](../README.md#ordem-de-apply-obrigatória-core-primeiro)). Veja
   [`infra/README.md`](../README.md) para o fluxo completo de produção.
