# Infraestrutura (Terraform) — vehicle-sales-service

Documentação da infraestrutura AWS **de produção** provisionada via Terraform: como está
estruturada, como configurar o backend remoto, quais variáveis/segredos são necessários e como
aplicar e fazer deploy. Para desenvolvimento local do serviço, veja o
[README raiz](../README.md); para validar esta infraestrutura localmente com um emulador AWS, veja
[`infra/local/README.md`](./local/README.md).

Esta é a **segunda** stack de infraestrutura da plataforma. O `vehicle-core-service` já provisiona
uma stack equivalente (mesmo módulo, recursos com nomes trocados) na mesma conta AWS. As duas
stacks são independentes exceto em um ponto: o provider OIDC do GitHub, que é compartilhado — ver
[O provider OIDC é um recurso compartilhado, e o Core é dono dele](#o-provider-oidc-é-um-recurso-compartilhado-e-o-core-é-dono-dele).

## Visão geral da arquitetura

Instância própria **EC2** (`t3.micro`, Amazon Linux 2023) rodando a aplicação via `docker compose`,
banco **RDS PostgreSQL** próprio, imagens em **ECR** próprio. Mesma decisão de arquitetura do
`vehicle-core-service` (MVP acadêmico: custo mínimo, sem alta disponibilidade, `t3.micro` +
`db.t4g.micro`, sem multi-AZ). As duas instâncias EC2 e ambos os bancos RDS ficam na **VPC default**
e nas **mesmas subnets** — condição necessária para a comunicação por IP privado descrita em
[URLs entre serviços devem usar IP privado](#urls-entre-serviços-devem-usar-ip-privado-nunca-o-endpoint-público).

## Layout

```
infra/
├── stack/    # módulo compartilhado: TODOS os recursos (SG, EC2, EIP, RDS, ECR, IAM, OIDC, KMS, SSM)
├── main/     # raiz de produção — Terraform Cloud (bloco cloud), executada por .github/workflows/infra.yml
└── local/    # raiz de teste local — mesmo módulo apontado para o Floci, estado local
deploy/
├── docker-compose.prod.yml   # compose autocontido de produção (apenas migrations + app)
└── deploy.sh                 # executado na EC2 via SSM Run Command
```

Princípio de design: **a stack de produção nunca é modificada para emulação** — a raiz `local/`
apenas alterna variáveis do módulo (`aws_endpoint_url`, `enable_github_oidc`). Ver detalhes de uso
local em [`infra/local/README.md`](./local/README.md).

## Recursos provisionados (módulo `stack`)

- **Security Group da aplicação:** entrada liberada apenas na porta `8000/tcp` (sem SSH — acesso
  via SSM), saída livre.
- **EC2 `t3.micro` + Elastic IP:** IMDSv2 obrigatório (hop limit 1), disco `gp3` criptografado;
  `user_data` instala Docker + plugin de compose fixado por versão, verificado via
  `sha256sum -c` contra o `checksums.txt` oficial do release.
- **RDS PostgreSQL 17** (`db.t4g.micro`, single-AZ, 20 GB `gp3` criptografado, sem acesso público);
  Security Group dedicado aceitando a porta 5432 **apenas do SG da aplicação**; senha master
  gerenciada pelo **Secrets Manager** (nunca aparece no state do Terraform); sem proteção contra
  exclusão nem snapshot final (MVP estudantil — o `destroy` precisa funcionar).
- **Repositório ECR** `vehicle-sales-service`: scan automático no push, tags mutáveis (permite mover
  `latest`), `force_delete`, política de ciclo de vida mantendo as últimas 10 imagens.
- **Instance profile IAM:** `AmazonSSMManagedInstanceCore` + leitura do segredo master do RDS +
  pull no repositório ECR da aplicação (nenhuma credencial de registry em lugar nenhum) **+ um
  `Deny` explícito** em `ssm:GetParameter`/`GetParameters`/`GetParametersByPath` sobre
  `parameter/vehicle-core-service/*`. Necessário porque `AmazonSSMManagedInstanceCore` libera
  `ssm:GetParameter*` em `Resource: "*"` — sem o `Deny`, a instância do Sales poderia ler os
  parâmetros `String` (não segredos, mas ainda assim de outro serviço) do Core. Um `Deny` explícito
  sempre vence um `Allow` no mesmo principal, então a ordem dos statements não importa. O Core tem a
  policy simétrica negando o prefixo do Sales.
- **Provider OIDC do GitHub + role de deploy** (`vehicle-sales-service-deploy`): trust fixado nas
  **duas formas exatas** do `sub` — `repo:<org>/vehicle-sales-service:ref:refs/heads/main` e
  `repo:<org>@<owner_id>/vehicle-sales-service@<repo_id>:ref:refs/heads/main` (`aud`/`sub` exatos,
  sem wildcard — mesmo raciocínio documentado em
  `vehicle-core-service/infra/README.md#oidc-do-github-actions-o-sub-real-usa-identificadores-imutáveis-id`);
  política permite `ssm:SendCommand` (documento `AWS-RunShellScript`, instância filtrada por tag),
  `ssm:GetCommandInvocation`, `ec2:DescribeInstances` e autenticação/push no único repositório ECR.
  **O provider em si não é criado aqui** — ver a seção dedicada abaixo.
- **KMS CMKs dedicadas** (rotação habilitada, ~US$ 1/mês cada):
  - `alias/vehicle-sales-service-ssm`: cifra os parâmetros `SecureString` do SSM deste serviço em
    vez da chave padrão da conta (`alias/aws/ssm`). A política da chave concede `kms:Decrypt` apenas
    à role da instância (via SSM, na região) + delegação de administração para a conta root.
  - `alias/vehicle-sales-service-rds`: cifra o storage do RDS **e** o segredo da senha master no
    Secrets Manager, referenciada explicitamente (`kms_key_id` /
    `master_user_secret_kms_key_id`). Sem chave explícita o RDS usaria as chaves gerenciadas
    `aws/rds` e `aws/secretsmanager`, inacessíveis à TFC run role de menor privilégio.

  Ambas recebem `tags` explícitas (não só via `default_tags`), pelo mesmo motivo documentado no
  README do Core: as permissões KMS da run role são condicionadas por tag, e `default_tags` não
  propaga de forma confiável para `aws_kms_key`. **A mesma corrida de propagação de tags do KMS
  (RDS chamando `DescribeKey` segundos após o `CreateKey`, o provider chamando `EnableKeyRotation`
  logo em seguida) já mordeu este projeto no Core** e a correção — statements
  `KmsBootstrapAndReadKeys`/`KmsUsageViaIntegratedServices` condicionados por
  `aws:RequestedRegion`/`kms:ViaService` em vez de tag — foi replicada aqui desde o primeiro apply.
  Detalhamento completo do incidente:
  `vehicle-core-service/infra/README.md#condições-por-tag-abac-nunca-guardam-ações-do-mesmo-run-que-cria-o-recurso`.
- **Parâmetros SSM** sob `/vehicle-sales-service/*`:
  - `SecureString` com valores placeholder (definidos fora do Terraform, com `ignore_changes`),
    cifrados com o CMK dedicado: `CORE_SERVICE_BASE_URL`, `CORE_SERVICE_TIMEOUT_SECONDS`,
    `INTERNAL_API_TOKEN`, `PAYMENT_WEBHOOK_TOKEN`, `SERVICE_NAME`, `DEBUG`, `LOG_LEVEL`. **O
    `deploy.sh` recusa o deploy (`exit 1`) se algum deles ainda estiver com o placeholder
    `CHANGE_ME`.**
  - `String` gerenciados pelo Terraform (derivados do RDS, não são segredos): `DATABASE_HOST`,
    `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_NAME`, `DATABASE_PASSWORD_SECRET_ARN`.

Custo estimado: EC2 `t3.micro` (~US$ 8/mês) + RDS `db.t4g.micro` (~US$ 12/mês) + 36 GB `gp3`
(~US$ 4/mês) + 2 KMS CMKs (~US$ 2/mês) ≈ **US$ 26/mês**, adicionais ao custo do Core. **Esta
instância NÃO é elegível ao free tier**: as cotas de 750h/mês de EC2 e de RDS são por conta AWS, não
por instância, e já são consumidas pela instância do `vehicle-core-service`. Diferente do README do
Core (que ainda descreve as duas instâncias como elegíveis ao free tier em contas novas), a partir
do momento em que este stack existe na mesma conta, o custo real passa a ser a soma das duas.

## O provider OIDC é um recurso compartilhado, e o Core é dono dele

A AWS permite **um único** `aws_iam_openid_connect_provider` por URL por conta — não é possível
cada serviço criar o seu para `token.actions.githubusercontent.com`. O `vehicle-core-service` foi o
primeiro a existir e é quem **cria e possui** o provider (`prevent_destroy = true` no recurso dele).
Esta stack **lê** esse provider com uma data source em vez de criar o próprio.

### Duas flags, deliberadamente separadas

```hcl
variable "create_github_oidc_provider" {
  default = false  # AWS só permite 1 provider por URL por conta; o Core já é dono do dele.
}
variable "enable_github_oidc" {
  default = true   # false SOMENTE na raiz local do Floci.
}
```

- **`create_github_oidc_provider`** (padrão `false` aqui) — decide se esta stack **cria** o
  provider OIDC (`aws_iam_openid_connect_provider`, recurso condicional) ou **lê** o que já existe
  (`data.aws_iam_openid_connect_provider`, também condicional — exatamente um dos dois está ativo).
  Continua `false` enquanto o Core existir na mesma conta. Se o Core for desativado/destruído e este
  serviço precisar assumir a posse do provider, essa é a flag a inverter — nesse caso lembre que o
  destroy do Core falha ao tentar destruir o provider por causa do `prevent_destroy` de lá (ver
  abaixo), então a posse muda de mãos via `terraform state rm` no Core antes de virar `true` aqui.
- **`enable_github_oidc`** (padrão `true`) — controla **apenas a role de deploy** (e, por tabela, se
  a data source/o recurso do provider são avaliados). É `false` **somente** na raiz `infra/local`
  (Floci): o emulador não implementa nem `CreateOpenIDConnectProvider` nem
  `GetOpenIDConnectProvider`, então tanto o recurso quanto a data source precisam ser descontados lá
  — não só o recurso, como no Core.

**Por que não bastava uma flag só (como no Core).** No módulo do Core, uma única flag
(`create_github_oidc`) controla ao mesmo tempo a criação do provider **e** a criação da role de
deploy — funciona porque o Core sempre cria seu próprio provider (ou nenhum dos dois, no Floci). Se
esta stack reaproveitasse a mesma flag única, `false` (o valor correto em produção, já que o
provider é do Core) desligaria **também** a role de deploy, e este serviço ficaria sem identidade de
CD nenhuma — `deploy_role_arn` sairia `null` mesmo em produção. As duas flags existem para separar
duas perguntas diferentes: "quem é dono do provider" (`create_github_oidc_provider`) e "este
ambiente tem uma role de deploy" (`enable_github_oidc`).

### Ordem de apply obrigatória: Core primeiro

Como esta stack lê o provider do Core via data source, **a infraestrutura do Core precisa já estar
aplicada** antes do primeiro `apply` desta stack. Se a ordem for invertida, o `plan` (não só o
`apply`) falha na leitura da data source — sintoma típico: erro do tipo *"no OpenID Connect Provider
found"* apontando para `data.aws_iam_openid_connect_provider.github`. Não há como contornar isso
sem inverter `create_github_oidc_provider = true` aqui (o que duplicaria o provider e quebraria a
regra de um-por-conta, ou falharia com `EntityAlreadyExists` se o do Core ainda existir).

### `prevent_destroy` no Core, e o que isso significa para o destroy da conta inteira

O recurso do provider, no lado do Core, carrega:

```hcl
lifecycle {
  prevent_destroy = true
}
```

Destruir o provider quebraria o CD **dos dois** serviços de uma vez (a role de deploy do Core e a
data source desta stack dependem dele). Consequência prática: **derrubar a conta inteira exige uma
ordem deliberada** — primeiro `destroy` desta stack (Sales), depois `destroy` da stack do Core. Um
`destroy` do Core enquanto o provider ainda existe e tem `prevent_destroy` falha no plan-time,
listando explicitamente `aws_iam_openid_connect_provider.github` como o recurso protegido. Para
seguir mesmo assim é preciso um `terraform state rm aws_iam_openid_connect_provider.github`
deliberado no workspace do Core (ou remover temporariamente o bloco `lifecycle` do `.tf` e reaplicar
antes do destroy) — nunca um passo automático do pipeline.

## `github_repository_id` não tem default de propósito

```hcl
variable "github_repository_id" {
  # REPOSITORY-SPECIFIC and DELIBERATELY WITHOUT A DEFAULT
  type = string
}
```

Diferente de `github_owner_id` (que tem default — mesmo dono de conta do Core, mesmo `<owner_id>` em
ambos os repositórios), `github_repository_id` **não tem default**: o Terraform recusa o `plan` sem
essa variável definida explicitamente no workspace da TFC. É proposital — leia a seção
`vehicle-core-service/infra/README.md#oidc-do-github-actions-o-sub-real-usa-identificadores-imutáveis-id`
para o histórico completo do problema que essa variável resolve: o `sub` real emitido pelo GitHub
usa a forma `repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:refs/heads/main`, e um `repo_id` errado
(ou emprestado do Core) produz uma negação **opaca** de `AssumeRoleWithWebIdentity` — nada no log da
Action aponta para a causa.

Como encontrar o id correto deste repositório:

```bash
curl -s https://api.github.com/repos/<owner>/vehicle-sales-service | jq '.id'
```

Anote o valor (`<repo_id>`, um número) e defina-o como variável do workspace `vehicle-sales-infra`
na TFC — **nunca** o mesmo valor usado no workspace do Core: mesmo dono (`<owner_id>`), repositório
diferente, id diferente.

## Configuração do backend (Terraform Cloud / HCP Terraform)

A raiz `infra/main` usa um bloco `cloud {}` (execução e state remotos). Organização e workspace vêm
de variáveis de ambiente, não de variáveis do Terraform:

```bash
export TF_CLOUD_ORGANIZATION=<sua-organização-hcp-terraform>
export TF_WORKSPACE=vehicle-sales-infra
```

### Configurações do workspace (UI da TFC)

- Workspace `vehicle-sales-infra`, fluxo **CLI-driven** (sem conexão VCS).
- **Execution Mode:** Remote.
- **Apply Method:** Auto apply — o gate humano fica no ambiente `infra` do GitHub (revisores
  obrigatórios), não na TFC.
- **Terraform Working Directory:** `infra/main`. Com ele definido, a CLI precisa rodar a partir do
  diretório correspondente — o `infra.yml` já faz isso; o upload da configuração inclui `../stack`.

### Bootstrap do workspace (manual, uma única vez)

1. Criar o workspace na UI com as configurações da seção acima.
2. **Credenciais dinâmicas do provider são obrigatórias** — chaves AWS estáticas como variáveis de
   workspace são **proibidas**. Ver
   [Dynamic Provider Credentials da HCP Terraform para AWS](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/aws-configuration).
3. Criar a **TFC run role** a partir dos arquivos de política já versionados no repositório
   (`infra/tfc-run-role-trust-policy.json` e `infra/tfc-run-role-policy.json`), usando uma
   identidade admin/bootstrap.

   Pela **CLI** (antes, edite os 3 placeholders em `tfc-run-role-trust-policy.json` — ver
   sub-passo 2 abaixo):

   ```bash
   cd infra
   aws iam create-role --role-name vehicle-sales-infra-tfc \
     --assume-role-policy-document file://tfc-run-role-trust-policy.json

   aws iam put-role-policy --role-name vehicle-sales-infra-tfc \
     --policy-name vehicle-sales-infra-tfc-policy \
     --policy-document file://tfc-run-role-policy.json
   ```

   Repare que, diferente do bootstrap do Core, **não há `aws iam create-open-id-connect-provider`
   aqui** — o provider `app.terraform.io` (usado pelas credenciais dinâmicas da TFC) é distinto do
   provider `token.actions.githubusercontent.com` (usado pelo deploy do GitHub Actions) e precisa
   existir mesmo assim; se a conta ainda não o tiver de quando o Core foi criado, crie-o seguindo o
   passo equivalente do `vehicle-core-service/infra/README.md`.

   Ou pelo **console** (IAM), em vez da CLI:

   1. *Roles* → *Create role* → **Web identity** → provider `app.terraform.io` → crie a role e edite
      a trust policy colando o conteúdo integral de `tfc-run-role-trust-policy.json`.
   2. No JSON colado, substitua **exatamente 3 placeholders**: `<AWS_ACCOUNT_ID>` (ID numérico da
      conta), `<TFC_ORG>` (organização da HCP Terraform) e `<TFC_PROJECT>` (projeto que contém o
      workspace — `Default Project` caso você não tenha criado nenhum). Nada mais precisa mudar.
   3. Na role, *Add permissions* → *Create inline policy* → JSON, colando
      `tfc-run-role-policy.json` (ajuste `aws:RequestedRegion` se não usar `us-east-1`).
   4. Copie o **ARN da role** — ele é o valor de `TFC_AWS_RUN_ROLE_ARN` no passo 4 abaixo.

   - `tfc-run-role-trust-policy.json`: trust fixado em `aud = aws.workload.identity` e
     `sub = organization:<TFC_ORG>:project:<TFC_PROJECT>:workspace:vehicle-sales-infra:run_phase:*`
     — org/projeto/workspace exatos, wildcard apenas em `run_phase` (mesmo raciocínio do Core: uma
     única role cobre as fases `plan` e `apply`).
   - `tfc-run-role-policy.json`: permissões de menor privilégio, restritas a recursos
     `vehicle-sales-service*` sempre que a AWS permite. A única leitura fora desse escopo é
     `iam:GetOpenIDConnectProvider` sobre o provider compartilhado do GitHub (statement
     `ReadSharedGithubOidcProvider`) — **sem** `Create`/`Delete`/`UpdateOpenIDConnectProviderThumbprint`,
     ao contrário da policy do Core: esta run role fisicamente não consegue apagar nem alterar o
     provider do Core, mesmo que quisesse.

   > ⚠️ **Toda vez que `tfc-run-role-policy.json` mudar no repositório, re-cole o JSON na role.**
   > A inline policy da role **não** acompanha o git: o conteúdo do arquivo só chega à AWS quando
   > você o cola de novo (console: role `vehicle-sales-infra-tfc` → *Permissions* → policy inline →
   > *Edit* → JSON → *Save*; ou repita o `aws iam put-role-policy` acima). Depois disso, rode o
   > `infra.yml` novamente. Sintoma típico de policy desatualizada: `AccessDenied` ou
   > `KMSKeyNotAccessibleFault` no apply — o mesmo ponto cego documentado no README do Core: o
   > Floci nunca pega esse tipo de erro, porque não implementa autorização IAM.

4. Variáveis do workspace na TFC:
   - Ambiente: `TFC_AWS_PROVIDER_AUTH=true` e
     `TFC_AWS_RUN_ROLE_ARN=<ARN da role vehicle-sales-infra-tfc>`.
   - Terraform: `github_org` (obrigatória), `github_repository_id` (**obrigatória, sem default** —
     ver seção acima), opcionalmente `github_owner_id` / `aws_region` / `instance_type` /
     `create_github_oidc_provider` (mantenha `false` enquanto o Core existir).
   - **Nunca** defina `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` no workspace — credenciais
     estáticas conflitam com a autenticação dinâmica.
5. Variáveis de ambiente para o `terraform init` em `infra/main` (a CI também as define):
   `TF_CLOUD_ORGANIZATION=<org>`, `TF_WORKSPACE=vehicle-sales-infra` (o bloco `cloud {}` as lê).
6. Gerar um **token de time restrito ao time deste workspace** (nunca um token de usuário ou de
   organização inteira). Defina uma expiração (ex.: 90 dias) e rotacione periodicamente — ele será
   salvo no GitHub no passo 8.
7. Criar o **environment `infra` no GitHub** (nível de *Settings* do repositório — exige admin):
   *Settings* → *Environments* → *New environment* → nome `infra` (exato — o `infra.yml` o
   referencia) → habilite **Required reviewers** e adicione você mesmo → salve as regras de
   proteção. Sem esse environment o workflow ainda roda, porém **sem nenhum gate humano**; com ele,
   toda execução do `infra.yml` (apply **e** destroy) pausa aguardando aprovação.
8. Configurar no GitHub (*Settings* → *Secrets and variables* → *Actions*, nível do repositório) o
   mínimo que o primeiro run do `infra.yml` exige:
   - Secret `TF_API_TOKEN` = token de time do passo 6.
   - Variável `TF_CLOUD_ORGANIZATION` = sua organização na HCP Terraform.
   - Variável `TF_WORKSPACE` = `vehicle-sales-infra`.

   Os demais secrets/variáveis dependem de outputs do Terraform e só entram **depois** do primeiro
   apply (seção seguinte). A tabela consolidada fica em
   [Segredos e variáveis do GitHub Actions](#segredos-e-variáveis-do-github-actions).
9. Configurar o **SonarCloud** — mesmo procedimento do Core (login com GitHub, importar o
   repositório `vehicle-sales-service`, desligar Automatic Analysis, gerar token, configurar
   `SONAR_TOKEN`/`SONAR_PROJECT_KEY`/`SONAR_ORGANIZATION` no GitHub). Sem `SONAR_TOKEN` os steps do
   Sonar são pulados sem quebrar a CI/CD; com ele, o CI analisa PRs e o CD bloqueia o deploy se o
   quality gate reprovar.

### Primeiro apply → secrets/variáveis pós-apply (destravam o `cd.yml`)

1. Rode o workflow `infra.yml` (ou, a partir de `infra/main`: `terraform init && terraform apply`
   com as variáveis de ambiente acima). **Confirme antes que o Core já foi aplicado** — ver
   [Ordem de apply obrigatória](#ordem-de-apply-obrigatória-core-primeiro).
2. Com os outputs do apply, configure no GitHub (mesmo caminho do passo 8 do bootstrap — nível do
   repositório):
   - Secret `AWS_ROLE_ARN` = output `deploy_role_arn`.
   - Variável `AWS_REGION` = mesma região de `aws_region` (`us-east-1` por padrão).
   - Variável opcional `APP_PUBLIC_IP` = output `elastic_ip` (usada no smoke test externo da CD).
3. Esses valores destravam o `cd.yml` (deploy), não o `infra.yml`: até o secret `AWS_ROLE_ARN`
   existir, o job de deploy da CD não consegue assumir a role (efeito ovo-e-galinha esperado).

## Aplicando a infraestrutura

Manualmente, a partir de `infra/main`:

```bash
cd infra/main
terraform init -input=false
terraform validate
terraform plan -input=false
terraform apply -auto-approve -input=false
```

Ou disparando o workflow **Infra** (`workflow_dispatch`) no GitHub Actions — protegido pelo
ambiente `infra` (requer revisores aprovadores configurados em *Settings > Environments*) e, para
`destroy`, pela confirmação explícita do input `confirm = vehicle-sales-service`.

## Segredos que precisam ser configurados fora do Terraform

Três parâmetros `SecureString` nascem com o placeholder `CHANGE_ME` (definido pelo Terraform, com
`lifecycle.ignore_changes` sobre o valor) e **precisam ser configurados manualmente, uma vez por
ambiente**, depois do primeiro apply. O `deploy.sh` recusa o deploy (imprimindo apenas os **nomes**
das chaves, nunca valores) enquanto qualquer um deles ainda estiver `CHANGE_ME`:

```bash
aws ssm put-parameter --overwrite --type SecureString \
  --name /vehicle-sales-service/INTERNAL_API_TOKEN --value '<mesmo valor definido no Core>'

aws ssm put-parameter --overwrite --type SecureString \
  --name /vehicle-sales-service/PAYMENT_WEBHOOK_TOKEN --value '<token aleatório com 32+ bytes, único>'

aws ssm put-parameter --overwrite --type SecureString \
  --name /vehicle-sales-service/CORE_SERVICE_BASE_URL --value 'http://<ip-privado-do-core>:8000'
# repita para: CORE_SERVICE_TIMEOUT_SECONDS, SERVICE_NAME, DEBUG, LOG_LEVEL
```

- **`INTERNAL_API_TOKEN`** — precisa ser **byte-idêntico** ao valor configurado no
  `/vehicle-core-service/INTERNAL_API_TOKEN` do Core. É o token comparado em tempo constante nas
  chamadas internas entre serviços (`X-Internal-Token`); qualquer divergência — um espaço a mais,
  um caractere trocado — faz **toda** chamada interna retornar 401, dos dois lados.
- **`PAYMENT_WEBHOOK_TOKEN`** — exclusivo do Sales, valida o header `X-Webhook-Token` do webhook de
  pagamento voltado para a internet (`POST /webhooks/v1/payments`). **Nunca deve compartilhar valor
  com `INTERNAL_API_TOKEN`**: são superfícies de ataque diferentes — o webhook é exposto
  publicamente (provedor de pagamento externo), o token interno não é. Reaproveitar o mesmo segredo
  para os dois faria um vazamento do webhook (mais exposto) comprometer também a comunicação
  interna entre serviços.
- **`CORE_SERVICE_BASE_URL`** — ver a seção seguinte: deve apontar para o **IP privado** da
  instância do Core, não para um endpoint público.

## URLs entre serviços devem usar IP privado, nunca o endpoint público

As duas instâncias EC2 (Core e Sales) vivem na **mesma VPC default** e na **mesma subnet** (ambas
usam `data.aws_subnets.default.ids[0]`), então conseguem se alcançar diretamente por IP privado, sem
sair para a internet. `CORE_SERVICE_BASE_URL` (aqui) e `SALES_SERVICE_BASE_URL` (no Core) devem
apontar para o **IP privado** da instância par (`http://<ip-privado>:8000`), não para o Elastic IP
público nem para um hostname de rede Docker (que não existe mais — ver
[Deploy](#deploy-deploy)).

**Por quê.** As chamadas entre serviços carregam `INTERNAL_API_TOKEN` em texto puro no header
`X-Internal-Token` — não há TLS entre eles (MVP estudantil, sem certificado/load balancer). Se a URL
apontar para o IP público, esse token trafega pela internet aberta a cada chamada interna. Pelo IP
privado, o tráfego nunca sai da VPC.

**O trade-off.** Um IP privado de instância EC2 muda se a instância for recriada (troca de
`instance_type`, recriação forçada por mudança de AMI, etc. — qualquer `apply` que force
`replace`). Isso significa que **toda substituição de instância** de um dos dois serviços passa a
exigir dois `aws ssm put-parameter --overwrite` adicionais no runbook: um no próprio serviço (se o
IP mudou e algo aponta para ele) e um no serviço par (atualizando a URL que aponta para o novo IP).
Não há automação para isso hoje — é um passo manual, fácil de esquecer, que quebra a comunicação
entre serviços silenciosamente até alguém notar 5xx/timeout nas chamadas internas.

## Por que `PAYMENT_WEBHOOK_TOKEN` nunca é escrito no `.env`

Mesma armadilha documentada no README do Core para `INTERNAL_API_TOKEN`, aqui reaplicada a um
terceiro segredo: o `docker compose` interpola `${...}` dentro dos valores lidos via `env_file`. Um
segredo gerado com `$` ou `{` na string (o caso mais comum: a senha do RDS, gerada pelo Secrets
Manager) seria truncado silenciosamente ou quebraria o deploy com `Invalid template`. Por isso os
três segredos (`DATABASE_PASSWORD`, `INTERNAL_API_TOKEN`, `PAYMENT_WEBHOOK_TOKEN`) são exportados no
processo shell do `deploy.sh` e passados ao Compose pela forma **sem valor** (`environment: -
PAYMENT_WEBHOOK_TOKEN`), que copia a variável verbatim do ambiente do daemon — sem parsing de
dotenv, sem interpolação, em qualquer versão do Compose.

**O detalhe que torna isso obrigatório mesmo no container de migrations.** O container `migrations`
nunca usa `PAYMENT_WEBHOOK_TOKEN` — ele só roda `alembic upgrade head`. Mas `alembic/env.py` chama
`get_settings()` na importação do módulo, para montar a `sqlalchemy.url`, e isso constrói o objeto
`Settings` completo — e `PAYMENT_WEBHOOK_TOKEN` é um campo obrigatório sem default. Sem ele, o
container de migrations morre com um `pydantic.ValidationError` antes mesmo de tentar conectar no
banco. Por isso `docker-compose.prod.yml` declara `PAYMENT_WEBHOOK_TOKEN` (e `INTERNAL_API_TOKEN`)
no serviço `migrations` também, não só no serviço da aplicação.

## Isolamento entre os dois serviços: real no plano de dados, aproximado no plano de controle

A intenção de projeto é isolamento total entre Core e Sales — bancos separados, EC2 separadas, CMKs
separadas. Vale a pena ser honesto sobre até onde isso realmente se sustenta.

**No plano de dados, o isolamento é real.** EC2 separada, RDS separado, CMK separada por serviço, e
os parâmetros SSM `SecureString` de cada serviço só são decifráveis pela role de instância do
próprio serviço (a política de cada CMK concede `kms:Decrypt` apenas à role da instância dona, via
`kms:ViaService`) — mais o `Deny` explícito descrito em
[Recursos provisionados](#recursos-provisionados-módulo-stack) que impede cada instância de sequer
**ler** os parâmetros `String` (não secretos) do serviço par.

**No plano de controle do Terraform, o isolamento é apenas aproximado.** Duas lacunas conhecidas,
ambas herdadas da mesma decisão de design do Core (condicionar por `kms:ViaService`/região em vez de
tag para evitar a corrida de propagação de ABAC — ver
[Recursos provisionados](#recursos-provisionados-módulo-stack)):

- **`KmsBootstrapAndReadKeys`** e **`KmsUsageViaIntegratedServices`** — os statements da run role do
  Sales que cobrem leitura/uso de qualquer CMK — são restritos por **região**
  (`aws:RequestedRegion`) e por **`kms:ViaService`**, não por tag de recurso. Isso significa que a
  run role de Terraform do Sales estruturalmente **alcança também as CMKs do Core** (e vice-versa):
  ela consegue `DescribeKey`, `GetKeyRotationStatus`, `Decrypt`/`Encrypt` via EC2/RDS/Secrets
  Manager/SSM sobre **qualquer** chave da região, não só as tagueadas `Service =
  vehicle-sales-service`. Apertar isso para exigir a tag reintroduziria exatamente a falha de
  propagação de ABAC documentada no README do Core (`KMSKeyNotAccessibleFault` no mesmo run que cria
  a chave) — o trade-off foi aceito conscientemente lá, e se propaga para cá.
- **`RdsManagedMasterSecret`** — o statement que cobre o ciclo de vida do segredo master gerenciado
  pelo RDS usa o recurso `arn:aws:secretsmanager:*:*:secret:rds!*` (o prefixo `rds!` documentado
  pela AWS para segredos criados pelo próprio RDS, sem alternativa mais restrita — ver a justificativa
  completa no README do Core). Isso significa que a run role do Sales tem `DeleteSecret` e
  `RotateSecret` sobre o segredo master **do Core** também, e a do Core sobre o do Sales. **Não**
  inclui `secretsmanager:GetSecretValue`: nenhuma das duas run roles consegue **ler** a senha do
  banco da outra — só ações de ciclo de vida (criar/tagear/rotacionar/apagar o segredo em si).

Nenhuma das duas é explorável remotamente (só a run role da TFC as tem, e ela já é um alvo de alto
privilégio por si só) — mas ambas são reais e valem ser conhecidas antes de assumir "isolamento
total" como garantia de segurança em profundidade.

## Toda alteração na policy exige vistoria manual — ela não falha no `plan`

A `tfc-run-role-policy.json` é o **único artefato da stack que nenhuma validação local consegue
exercitar**. `terraform validate` não a lê, `terraform plan` não a exercita (o plan só faz leituras),
e o Floci autoriza qualquer chamada porque não implementa o motor de autorização do IAM. Ela só é
testada no `apply` — e falha no meio dele, com recursos já criados.

Regra, portanto: **toda mudança em `infra/stack/*.tf` ou na própria policy pede uma vistoria
recurso-a-recurso**, mapeando cada `resource` para o statement que o autoriza nas quatro fases
(create, plan/refresh, update, destroy). Não confie em "copiei de uma policy que funciona": herdar
cobre os recursos idênticos, mas **cada edição deliberada é uma hipótese não testada**.

Atenção especial a dois casos que não são óbvios lendo o Terraform:

1. **Permissões que a AWS exige do *chamador* por efeitos colaterais de serviço.** Não existe nenhum
   `aws_secretsmanager_secret` neste código, e ainda assim `secretsmanager:CreateSecret` é
   obrigatória: `manage_master_user_password = true` faz o RDS criar o segredo usando as permissões
   de quem chamou. Ler o `.tf` nunca revelaria isso — só a doc do serviço.
2. **Remoções.** Adicionar permissão em excesso falha silenciosamente para o lado seguro; **remover**
   falha no apply. Este repositório já tem um caso concreto: numa limpeza de menor privilégio,
   `arn:aws:rds:*:*:pg:*` foi retirado do statement `RdsManageDbInstance` sob o argumento de que
   nenhuma stack cria parameter group. Está errado — o
   [exemplo oficial da AWS para `rds:CreateDBInstance`](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/security_iam_id-based-policy-examples-create-and-modify-examples.html)
   inclui o ARN `pg:`, e a verificação de autorização ocorre **mesmo sem `parameter_group_name`
   definido**, porque o RDS usa o parameter group *default*. O ARN foi restaurado antes do primeiro
   apply, numa vistoria como a descrita aqui. O `secgrp:*`, removido na mesma limpeza, é de fato
   desnecessário (resquício de EC2-Classic) e continua fora.

## O caminho de `destroy` nunca foi exercitado

Nem esta stack nem a do Core já passaram por um `destroy` real contra a AWS. As ações de destruição
existem na policy (`ec2:TerminateInstances`, `rds:DeleteDBInstance`, `kms:ScheduleKeyDeletion`,
`iam:DeleteRole`, `ecr:DeleteRepository`, `ssm:DeleteParameter`, `secretsmanager:DeleteSecret`),
mas permanecem **não verificadas** até o primeiro destroy real de cada workspace. Trate qualquer
`AccessDenied` nesse momento como lacuna da policy, não como bug do Terraform — corrija o JSON,
re-cole na AWS, repita.

Uma peculiaridade nova nesta topologia: **o `destroy` do Core, a partir de agora, falha por
projeto** ao tentar destruir o provider OIDC compartilhado, por causa do `prevent_destroy` — ver
[`prevent_destroy` no Core](#prevent_destroy-no-core-e-o-que-isso-significa-para-o-destroy-da-conta-inteira).
Isso não é um bug a corrigir: é a barreira deliberada contra derrubar a conta inteira na ordem
errada. O destroy desta stack (Sales) não tem essa trava — ela nunca é dona do provider.

## Deploy (`deploy/`)

O deploy é feito pelo workflow `cd.yml` a cada push em `main`: build e push da imagem para o ECR,
depois execução remota na instância EC2 via **AWS Systems Manager (SSM Run Command)** — não há SSH
nem checkout de repositório na instância.

- **`deploy/docker-compose.prod.yml`** — compose autocontido para a EC2: usa a imagem já publicada
  no ECR (`APP_IMAGE`) em vez de `build:`. Diferenças em relação ao `docker-compose.yml` de
  desenvolvimento local: sem serviço `postgres` (o banco é o RDS) e sem serviço `seed` (dados de
  demonstração nunca são inseridos em produção). **Sem a rede `vehicle-platform`** usada pelo Core:
  Core e Sales rodam em instâncias EC2 **separadas**, então uma bridge Docker compartilhada não
  consegue carregar tráfego entre elas de qualquer forma — a comunicação entre serviços vai sempre
  pelo `CORE_SERVICE_BASE_URL` configurado (ver
  [URLs entre serviços devem usar IP privado](#urls-entre-serviços-devem-usar-ip-privado-nunca-o-endpoint-público)),
  nunca por resolução de nome de container entre hosts. Sobe `migrations` (`alembic upgrade head`) e
  depois o serviço da aplicação, com healthcheck em `/health`.
- **`deploy/deploy.sh`** — script executado na instância pelo comando SSM:
  1. Materializa `/opt/vehicle-sales-service/.env` lendo os parâmetros SSM não-secretos
     (`--with-decryption`), mais os três segredos (`DATABASE_PASSWORD` via Secrets Manager,
     `INTERNAL_API_TOKEN` e `PAYMENT_WEBHOOK_TOKEN` via SSM `SecureString`) exportados apenas no
     ambiente do processo — ver
     [Por que `PAYMENT_WEBHOOK_TOKEN` nunca é escrito no `.env`](#por-que-payment_webhook_token-nunca-é-escrito-no-env).
     Nenhum valor passa pelos parâmetros do `SendCommand` nem é logado.
  2. Recusa o deploy se qualquer parâmetro SSM ainda estiver com o valor `CHANGE_ME`, ou se algum
     dos três segredos resolver para uma string vazia (nomes de chave impressos, nunca valores).
  3. Autentica no ECR usando a role da instância, faz `pull` da imagem recebida como argumento e
     sobe a stack com `docker compose -f docker-compose.prod.yml up -d`.
  4. Aguarda `/health` responder; falha o comando SSM (e o job da CD) se o serviço não ficar
     saudável.

O workflow `cd.yml` envia `deploy.sh` e `docker-compose.prod.yml` do próprio checkout para a
instância (em base64, pelo canal do SSM) antes de executar o deploy — o `user_data` da EC2 apenas
prepara o Docker, o repositório é a fonte da verdade dos artefatos de deploy.

## Variáveis de ambiente e segredos

Todos os nomes abaixo correspondem exatamente ao arquivo
[`service/env.example`](../service/env.example) do serviço. **Nunca** commite valores reais — apenas
os nomes das chaves.

| Variável | Descrição | Exemplo | Origem em produção |
|---|---|---|---|
| `DATABASE_HOST` | Host do PostgreSQL | `vehicle-sales-db.xxxxx.us-east-1.rds.amazonaws.com` | Terraform (endpoint do RDS) |
| `DATABASE_PORT` | Porta do PostgreSQL | `5432` | Terraform (porta do RDS) |
| `DATABASE_USER` | Usuário de conexão com o banco | `vehicle_sales_user` | Terraform (usuário master do RDS) |
| `DATABASE_PASSWORD` | Senha de conexão com o banco | *(gerada, não versionada)* | Secrets Manager, referenciado pela SSM `DATABASE_PASSWORD_SECRET_ARN`; materializada em runtime pelo `deploy.sh` |
| `DATABASE_NAME` | Nome do banco de dados | `vehicle_sales` | Terraform (nome do banco no RDS) |
| `CORE_SERVICE_BASE_URL` | URL base do `vehicle-core-service` | `http://<ip-privado-do-core>:8000` | SSM `SecureString` (`CHANGE_ME` até ser definida manualmente — use o IP privado, não o público) |
| `CORE_SERVICE_TIMEOUT_SECONDS` | Timeout, em segundos, das chamadas HTTP ao serviço de catálogo | `5.0` | SSM `SecureString` |
| `INTERNAL_API_TOKEN` | Token compartilhado exigido no header `X-Internal-Token` das rotas internas entre serviços — **byte-idêntico** ao do Core | *(string aleatória com 32+ bytes)* | SSM `SecureString` |
| `PAYMENT_WEBHOOK_TOKEN` | Token exigido no header `X-Webhook-Token` do webhook de pagamento — exclusivo do Sales, nunca compartilha valor com `INTERNAL_API_TOKEN` | *(string aleatória com 32+ bytes, distinta do token interno)* | SSM `SecureString` |
| `SERVICE_NAME` | Nome do serviço usado em logs e no health check | `vehicle-sales-service` | SSM `SecureString` |
| `DEBUG` | Habilita modo debug (echo de SQL, logs verbosos) | `false` | SSM `SecureString` |
| `LOG_LEVEL` | Nível mínimo de log | `INFO` | SSM `SecureString` |

`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER` e `DATABASE_NAME` são escritos automaticamente
pelo Terraform — nada a fazer. `DATABASE_PASSWORD` nunca fica no SSM: vive no segredo gerenciado
pelo RDS no Secrets Manager, referenciado pelo parâmetro `DATABASE_PASSWORD_SECRET_ARN`.

### Segredos e variáveis do GitHub Actions

| Nome | Tipo | Descrição |
|---|---|---|
| `AWS_ROLE_ARN` | Secret do repositório | ARN da role OIDC de deploy (output `deploy_role_arn` do Terraform) |
| `AWS_REGION` | Variável do repositório | Região AWS, deve coincidir com `aws_region` do Terraform |
| `TF_API_TOKEN` | Secret do repositório | Token de time da HCP Terraform, usado pelo workflow `infra.yml` |
| `TF_CLOUD_ORGANIZATION` | Variável do repositório | Organização na HCP Terraform |
| `TF_WORKSPACE` | Variável do repositório | Nome do workspace (`vehicle-sales-infra`) |
| `SONAR_TOKEN` | Secret do repositório | Token do SonarCloud (passo 9 do bootstrap); se ausente, os steps de análise são pulados sem quebrar a CI/CD |
| `SONAR_PROJECT_KEY` / `SONAR_ORGANIZATION` | Variáveis do repositório | Identificação do projeto no SonarCloud (passo 9 do bootstrap) |
| `APP_PUBLIC_IP` | Variável do repositório (opcional) | IP público (Elastic IP) usado no smoke test externo pós-deploy da CD |

## Referências

- [README raiz](../README.md) — visão geral do serviço, arquitetura de código e execução local.
- [`infra/local/README.md`](./local/README.md) — validação local da infraestrutura com o Floci.
- `vehicle-core-service/infra/README.md` — infraestrutura do outro serviço da plataforma: dono do
  provider OIDC compartilhado, histórico completo dos incidentes de propagação de tags do KMS, e o
  formato real do `sub` do OIDC do GitHub Actions.
