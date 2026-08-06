# Infraestrutura (Terraform) — vehicle-sales-service

Documentação da infraestrutura AWS **de produção** provisionada via Terraform: como aplicar, quais
variáveis/segredos configurar e como fazer deploy (Parte 1 — Runbook), e por que cada decisão foi
tomada (Parte 2 — Referência). Para desenvolvimento local do serviço, veja o
[README raiz](../README.md); para validar esta infraestrutura localmente com um emulador AWS, veja
[`infra/local/README.md`](./local/README.md).

## Sumário

**Parte 1 — Runbook**
1. [Pré-requisitos](#1-pré-requisitos)
2. [Tabela consolidada de variáveis e segredos](#2-tabela-consolidada-de-variáveis-e-segredos)
3. [Passo a passo](#3-passo-a-passo)
4. [Operação do dia a dia](#4-operação-do-dia-a-dia)

**Parte 2 — Referência e justificativas**
- [Recursos provisionados (módulo `stack`)](#recursos-provisionados-módulo-stack)
- [Custo estimado](#custo-estimado)
- [O provider OIDC é um recurso compartilhado, e o Core é dono dele](#o-provider-oidc-é-um-recurso-compartilhado-e-o-core-é-dono-dele)
- [Os identificadores imutáveis do GitHub (`github_owner_id` / `github_repository_id`)](#os-identificadores-imutáveis-do-github-github_owner_id--github_repository_id)
- [URLs entre serviços devem usar IP privado, nunca o endpoint público](#urls-entre-serviços-devem-usar-ip-privado-nunca-o-endpoint-público)
- [Por que `PAYMENT_WEBHOOK_TOKEN` nunca é escrito no `.env`](#por-que-payment_webhook_token-nunca-é-escrito-no-env)
- [Isolamento entre os dois serviços: real no plano de dados, aproximado no plano de controle](#isolamento-entre-os-dois-serviços-real-no-plano-de-dados-aproximado-no-plano-de-controle)
- [Toda alteração na policy exige vistoria manual — ela não falha no `plan`](#toda-alteração-na-policy-exige-vistoria-manual--ela-não-falha-no-plan)
- [O caminho de `destroy` nunca foi exercitado](#o-caminho-de-destroy-nunca-foi-exercitado)
- [Deploy (`deploy/`)](#deploy-deploy)
- [Referências](#referências)

---

# Parte 1 — Runbook

## 1. Pré-requisitos

- Terraform `>= 1.6.0`, AWS CLI configurada, acesso admin ao repositório no GitHub e a uma
  organização na HCP Terraform.
- **A infraestrutura do `vehicle-core-service` precisa estar aplicada antes do primeiro `apply`
  desta stack** — esta stack lê o provider OIDC do GitHub, dono do Core, via *data source* em tempo
  de `plan` (não só de `apply`). Ver
  [O provider OIDC é um recurso compartilhado, e o Core é dono dele](#o-provider-oidc-é-um-recurso-compartilhado-e-o-core-é-dono-dele).

## 2. Tabela consolidada de variáveis e segredos

Todo valor que precisa ser configurado em algum lugar para esta stack funcionar, de ponta a ponta
(Terraform → TFC → GitHub → SSM). "Quando" indica a ordem: **antes do primeiro apply**, **depois do
primeiro apply** ou **antes do primeiro deploy**.

| Nome | Tipo | Onde se configura | Valor / origem | Quando |
|---|---|---|---|---|
| `github_org` | variável Terraform (**sem** default — obrigatória) | workspace variable (TFC) — categoria *Terraform* | organização/usuário GitHub dono do repositório | antes do primeiro apply |
| `github_owner_id` | variável Terraform (já tem default) | workspace variable (TFC) — *Terraform*, opcional | default no código (`infra/main/main.tf`); só sobrescreva se o repositório mudar de dono | normalmente nunca |
| `github_repository_id` | variável Terraform (já tem default) | workspace variable (TFC) — *Terraform*, opcional | default no código (`infra/main/main.tf`); só sobrescreva se o repositório for recriado | normalmente nunca |
| `aws_region` | variável Terraform (já tem default) | workspace variable (TFC) — *Terraform*, opcional | default `us-east-1` | normalmente nunca |
| `instance_type` | variável Terraform (já tem default) | workspace variable (TFC) — *Terraform*, opcional | default `t3.micro` | normalmente nunca |
| `create_github_oidc_provider` | variável Terraform (já tem default) | workspace variable (TFC) — *Terraform*, opcional | default `false` — manter enquanto o Core existir na conta | normalmente nunca |
| `enable_github_oidc` | variável Terraform de uso interno do módulo | **não configurável nesta raiz** — `infra/main` não declara essa variável, então nenhum valor de workspace chega a ela | sempre resolve para o default do módulo (`true`) em produção; só é `false` na raiz `infra/local` | N/A em produção |
| `TFC_AWS_PROVIDER_AUTH` | workspace variable (TFC) — categoria *Environment* | workspace `vehicle-sales-infra`, aba *Variables* | `true` | antes do primeiro apply |
| `TFC_AWS_RUN_ROLE_ARN` | workspace variable (TFC) — categoria *Environment* | workspace `vehicle-sales-infra`, aba *Variables* | ARN da role `vehicle-sales-infra-tfc` (passo 2) | antes do primeiro apply |
| `TF_API_TOKEN` | GitHub secret (repositório) | *Settings → Secrets and variables → Actions → Secrets* | token de time da HCP Terraform, restrito ao workspace | antes do primeiro apply |
| `TF_CLOUD_ORGANIZATION` | GitHub repository variable | *Settings → Secrets and variables → Actions → Variables* | organização na HCP Terraform | antes do primeiro apply |
| `TF_WORKSPACE` | GitHub repository variable | idem | `vehicle-sales-infra` | antes do primeiro apply |
| `SONAR_TOKEN` | GitHub secret (repositório), opcional | idem, *Secrets* | token gerado no SonarCloud | antes do primeiro deploy |
| `SONAR_PROJECT_KEY` | GitHub repository variable, opcional | idem, *Variables* | project key do SonarCloud | antes do primeiro deploy |
| `SONAR_ORGANIZATION` | GitHub repository variable, opcional | idem, *Variables* | organization key do SonarCloud | antes do primeiro deploy |
| `AWS_ROLE_ARN` | GitHub secret (repositório) | idem, *Secrets* | output `deploy_role_arn` do Terraform | depois do primeiro apply |
| `AWS_REGION` | GitHub repository variable | idem, *Variables* | mesma região de `aws_region` | depois do primeiro apply |
| `APP_PUBLIC_IP` | GitHub repository variable, opcional | idem, *Variables* | output `elastic_ip` | depois do primeiro apply |
| `INTERNAL_API_TOKEN` | parâmetro SSM (`SecureString`) | `aws ssm put-parameter --overwrite` (fora do Terraform) | byte-idêntico ao `/vehicle-core-service/INTERNAL_API_TOKEN` do Core | depois do primeiro apply, antes do primeiro deploy |
| `PAYMENT_WEBHOOK_TOKEN` | parâmetro SSM (`SecureString`) | idem | string aleatória com 32+ bytes, exclusiva do Sales | depois do primeiro apply, antes do primeiro deploy |
| `CORE_SERVICE_BASE_URL` | parâmetro SSM (`SecureString`) | idem | `http://<ip-privado-do-core>:8000` | depois do primeiro apply, antes do primeiro deploy |
| `CORE_SERVICE_TIMEOUT_SECONDS` | parâmetro SSM (`SecureString`) | idem | `5` | depois do primeiro apply, antes do primeiro deploy |
| `SERVICE_NAME` | parâmetro SSM (`SecureString`) | idem | `vehicle-sales-service` | depois do primeiro apply, antes do primeiro deploy |
| `DEBUG` | parâmetro SSM (`SecureString`) | idem | `false` | depois do primeiro apply, antes do primeiro deploy |
| `LOG_LEVEL` | parâmetro SSM (`SecureString`) | idem | `INFO` | depois do primeiro apply, antes do primeiro deploy |
| `DATABASE_HOST` / `DATABASE_PORT` / `DATABASE_USER` / `DATABASE_NAME` / `DATABASE_PASSWORD_SECRET_ARN` | parâmetro SSM (`String`, gerenciado pelo Terraform) | escrito automaticamente a partir do `aws_db_instance.app` | derivado do RDS | automático — nenhuma ação |

> `DATABASE_PASSWORD` não aparece nesta tabela: nunca é configurado por ninguém. Vive no segredo
> gerenciado pelo RDS no Secrets Manager (`manage_master_user_password = true`) e é lido em runtime
> pelo `deploy.sh` via `DATABASE_PASSWORD_SECRET_ARN`.

## 3. Passo a passo

1. **Criar o workspace na HCP Terraform.**
   - Nome `vehicle-sales-infra`, fluxo **CLI-driven** (sem conexão VCS).
   - **Execution Mode:** Remote.
   - **Apply Method:** Auto apply (o gate humano fica no ambiente `infra` do GitHub, passo 5).
   - **Terraform Working Directory:** `infra/main`.
   - **Credenciais dinâmicas do provider são obrigatórias** — chaves AWS estáticas como variável de
     workspace são proibidas. Ver
     [Dynamic Provider Credentials da HCP Terraform para AWS](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/aws-configuration).
   - Localmente, `terraform init` em `infra/main` lê organização/workspace de variáveis de ambiente
     (o bloco `cloud {}` não aceita variáveis do Terraform):
     ```bash
     export TF_CLOUD_ORGANIZATION=<sua-organização-hcp-terraform>
     export TF_WORKSPACE=vehicle-sales-infra
     ```

2. **Criar a run role na AWS**, a partir dos dois JSONs já versionados em `infra/` — usando uma
   identidade admin/bootstrap.

   Pela **CLI** (edite antes os placeholders da trust policy — ver abaixo):
   ```bash
   cd infra
   aws iam create-role --role-name vehicle-sales-infra-tfc \
     --assume-role-policy-document file://tfc-run-role-trust-policy.json

   aws iam put-role-policy --role-name vehicle-sales-infra-tfc \
     --policy-name vehicle-sales-infra-tfc-policy \
     --policy-document file://tfc-run-role-policy.json
   ```
   Ou pelo **console** (IAM):
   1. *Roles* → *Create role* → **Web identity** → provider `app.terraform.io` → crie a role e
      edite a trust policy colando o conteúdo integral de `tfc-run-role-trust-policy.json`.
   2. Na role, *Add permissions* → *Create inline policy* → JSON, colando `tfc-run-role-policy.json`.
   3. Copie o **ARN da role** — é o valor de `TFC_AWS_RUN_ROLE_ARN` (tabela da seção 2).

   **Placeholders a substituir em cada arquivo:**
   - `tfc-run-role-trust-policy.json` — exatamente 3: `<AWS_ACCOUNT_ID>` (id numérico da conta),
     `<TFC_ORG>` (organização HCP Terraform), `<TFC_PROJECT>` (projeto do workspace — `Default
     Project` se você não criou nenhum).
   - `tfc-run-role-policy.json` — nenhum obrigatório; ajuste `aws:RequestedRegion` só se não usar
     `us-east-1`.

   Diferente do bootstrap do Core, **não rode `aws iam create-open-id-connect-provider`** aqui: o
   provider `app.terraform.io` já deve existir na conta (criado quando o Core foi bootstrapado). Se
   esta for a primeira stack da conta, crie-o seguindo o passo equivalente do
   `vehicle-core-service/infra/README.md` antes de continuar.

   > ⚠️ **Toda vez que `tfc-run-role-policy.json` mudar no repositório, re-cole o JSON na role.**
   > A inline policy da role **não** acompanha o git — o conteúdo do arquivo só chega à AWS quando
   > você o cola de novo:
   > ```bash
   > cd infra
   > aws iam put-role-policy --role-name vehicle-sales-infra-tfc \
   >   --policy-name vehicle-sales-infra-tfc-policy \
   >   --policy-document file://tfc-run-role-policy.json
   > ```
   > Ou no console: role `vehicle-sales-infra-tfc` → *Permissions* → policy inline → *Edit* → JSON →
   > *Save*. Só depois rode o `infra.yml` de novo. Sintoma típico de policy desatualizada:
   > `AccessDenied` ou `KMSKeyNotAccessibleFault` no apply.

3. **Configurar as variáveis do workspace na TFC**, conforme a tabela da seção 2 (categorias
   *Environment* e *Terraform*; só `github_org` é obrigatória, as demais já têm default). **Nunca**
   defina `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` como variável de workspace — credenciais
   estáticas conflitam com a autenticação dinâmica.

4. **Configurar o SonarCloud.**
   1. Em [sonarcloud.io](https://sonarcloud.io), login com GitHub → *Analyze new project* → importe
      o repositório `vehicle-sales-service` (anote *project key* e *organization key*).
   2. No projeto → *Administration* → *Analysis Method* → **desligue Automatic Analysis**
      (obrigatório — conflita com a análise via CI).
   3. *My Account* → *Security* → gere um token.
   4. Guarde token/project key/organization key para o passo seguinte.

5. **Configurar no GitHub (nível do repositório) o que o primeiro `apply` exige:**
   - Criar o **environment `infra`** (*Settings → Environments → New environment*, nome exato
     `infra`) com **Required reviewers** habilitado (adicione você mesmo). Sem ele o workflow roda
     sem nenhum gate humano.
   - *Settings → Secrets and variables → Actions*:
     - Secret `TF_API_TOKEN` (token de time gerado na TFC, escopo restrito ao workspace, com
       expiração definida).
     - Variáveis `TF_CLOUD_ORGANIZATION` e `TF_WORKSPACE=vehicle-sales-infra`.
     - Secret `SONAR_TOKEN` e variáveis `SONAR_PROJECT_KEY`/`SONAR_ORGANIZATION` (passo 4).

6. **Rodar o workflow `infra.yml`** (`workflow_dispatch`, `action=apply`) — protegido pelo ambiente
   `infra`. **Confirme antes que o Core já foi aplicado** (pré-requisito da seção 1). Alternativa
   manual, a partir de `infra/main`:
   ```bash
   cd infra/main
   terraform init -input=false
   terraform validate
   terraform plan -input=false
   terraform apply -auto-approve -input=false
   ```

7. **Configurar no GitHub os secrets/variáveis que só existem depois do apply**, usando os outputs
   do Terraform (mesmo caminho do passo 5):
   - Secret `AWS_ROLE_ARN` = output `deploy_role_arn`.
   - Variável `AWS_REGION` = mesma região de `aws_region`.
   - Variável opcional `APP_PUBLIC_IP` = output `elastic_ip` (habilita o smoke test externo da CD).

   Até `AWS_ROLE_ARN` existir, o job de deploy do `cd.yml` não consegue assumir a role — efeito
   ovo-e-galinha esperado.

8. **Configurar os 7 parâmetros SSM `SecureString`** (nascem com o placeholder `CHANGE_ME`; o
   `deploy.sh` recusa o deploy enquanto qualquer um estiver assim):
   ```bash
   P=/vehicle-sales-service

   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/INTERNAL_API_TOKEN --value '<mesmo valor configurado no Core>'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/PAYMENT_WEBHOOK_TOKEN --value '<token aleatório com 32+ bytes, único>'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/CORE_SERVICE_BASE_URL --value 'http://<ip-privado-do-core>:8000'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/CORE_SERVICE_TIMEOUT_SECONDS --value '5'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/SERVICE_NAME --value 'vehicle-sales-service'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/DEBUG --value 'false'
   aws ssm put-parameter --overwrite --type SecureString \
     --name $P/LOG_LEVEL --value 'INFO'
   ```
   `INTERNAL_API_TOKEN` precisa ser **byte-idêntico** ao configurado no Core; `CORE_SERVICE_BASE_URL`
   usa o **IP privado** da instância do Core, nunca o endpoint público — ver
   [URLs entre serviços devem usar IP privado](#urls-entre-serviços-devem-usar-ip-privado-nunca-o-endpoint-público).

9. **Rodar o workflow `cd.yml`** — dispara automaticamente em todo push em `main` que toque
   `service/**` ou `deploy/**`, ou manualmente via `workflow_dispatch`. Faz build/push da imagem no
   ECR e deploy remoto na EC2 via SSM Run Command.

10. **Verificação pós-deploy.**
    - O próprio `deploy.sh` já bloqueia o job da CD se `GET /health` (interno) não responder.
    - Se `APP_PUBLIC_IP` estiver configurado, o `cd.yml` roda também um smoke test externo:
      `curl http://<APP_PUBLIC_IP>:8000/health`.
    - Para inspecionar logs/estado remotamente, use SSM Run Command (`AWS-RunShellScript`) contra a
      instância marcada com a tag `Service=vehicle-sales-service`, executando
      `docker compose -f docker-compose.prod.yml ps` / `logs`.

11. **Fechar o círculo com o Core** — as duas URLs entre serviços precisam apontar para o **IP
    privado** do par:
    ```bash
    # IP privado desta instância (Sales), para configurar no Core:
    aws ec2 describe-instances \
      --filters "Name=tag:Service,Values=vehicle-sales-service" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].PrivateIpAddress" --output text

    # No workspace/conta do Core, atualize e reinicie o app para pegar o novo valor:
    aws ssm put-parameter --overwrite --type SecureString \
      --name /vehicle-core-service/SALES_SERVICE_BASE_URL --value 'http://<ip-privado-do-sales>:8000'
    ```
    `CORE_SERVICE_BASE_URL` (aqui, passo 8) já deve ter sido configurado com o IP privado do Core.
    Sem os dois lados apontando corretamente, as chamadas internas retornam timeout/5xx — ver
    [URLs entre serviços devem usar IP privado](#urls-entre-serviços-devem-usar-ip-privado-nunca-o-endpoint-público).

## 4. Operação do dia a dia

- **Redeploy** (mesma imagem ou nova versão): push em `main` tocando `service/**`/`deploy/**`, ou
  disparo manual do `cd.yml` (`workflow_dispatch`).
- **Alterar um segredo já configurado:**
  ```bash
  aws ssm put-parameter --overwrite --type SecureString \
    --name /vehicle-sales-service/<CHAVE> --value '<novo-valor>'
  ```
  Depois, rode o `cd.yml` — o `deploy.sh` só relê o SSM a cada deploy, um `put-parameter` isolado
  não reinicia o container.
- **Aplicar uma mudança de infraestrutura** (`infra/stack/*.tf`):
  1. Valide localmente com `./infra/local/floci-validate.sh --apply` antes de abrir o PR.
  2. Se a mudança tocou em permissões necessárias, revise `tfc-run-role-policy.json`
     recurso-a-recurso — ver
     [Toda alteração na policy exige vistoria manual](#toda-alteração-na-policy-exige-vistoria-manual--ela-não-falha-no-plan).
  3. Se `tfc-run-role-policy.json` mudou, **re-cole o JSON na role na AWS** (⚠️ do passo 2 — o git
     não propaga isso sozinho).
  4. Rode o `infra.yml` (`action=apply`).
- **Destruir a stack:** `infra.yml` (`action=destroy`, `confirm=vehicle-sales-service`) ou
  `terraform destroy` manual a partir de `infra/main`. Se a intenção é derrubar a conta inteira
  (Core + Sales), **destrua esta stack (Sales) primeiro** — ver
  [`prevent_destroy` no Core](#prevent_destroy-no-core-e-o-que-isso-significa-para-o-destroy-da-conta-inteira)
  e [O caminho de `destroy` nunca foi exercitado](#o-caminho-de-destroy-nunca-foi-exercitado).

---

# Parte 2 — Referência e justificativas

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

## Custo estimado

EC2 `t3.micro` (~US$ 8/mês) + RDS `db.t4g.micro` (~US$ 12/mês) + 36 GB `gp3` (~US$ 4/mês) + 2 KMS
CMKs (~US$ 2/mês) ≈ **US$ 26/mês**, adicionais ao custo do Core. **Esta instância NÃO é elegível ao
free tier**: as cotas de 750h/mês de EC2 e de RDS são por conta AWS, não por instância, e já são
consumidas pela instância do `vehicle-core-service`. Diferente do README do Core (que ainda descreve
as duas instâncias como elegíveis ao free tier em contas novas), a partir do momento em que este
stack existe na mesma conta, o custo real passa a ser a soma das duas.

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
  — não só o recurso, como no Core. Ela não está exposta em `infra/main` (produção sempre usa o
  default `true` do módulo — ver a tabela da seção 2).

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

## Os identificadores imutáveis do GitHub (`github_owner_id` / `github_repository_id`)

Ambas as variáveis já vêm com **default correto** no módulo (`infra/stack/variables.tf` e
`infra/main/main.tf`), do mesmo jeito que no Core — **não é preciso defini-las no workspace da TFC**.
O `github_owner_id` é o mesmo dos dois repositórios (mesma conta); o `github_repository_id` é
específico deste repositório e **diferente do valor usado no Core**.

Por que essas variáveis existem: o `sub` que o GitHub realmente emite usa a forma
`repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:refs/heads/main`, e a trust policy fixa strings
exatas. Um `repo_id` errado — tipicamente **emprestado do Core numa cópia de arquivo** — produz uma
negação **opaca** de `AssumeRoleWithWebIdentity`: nada no log da Action aponta para a causa, e todos
os campos visíveis parecem corretos. O histórico completo do incidente está em
`vehicle-core-service/infra/README.md#oidc-do-github-actions-o-sub-real-usa-identificadores-imutáveis-id`,
inclusive como diagnosticar pelo CloudTrail (o campo `userName` do evento **é** a claim `sub`).

Só mexa nesses valores se o repositório for **recriado** — o id é imutável a renomeações, que é
justamente o motivo de o GitHub usá-lo na claim. Se precisar reconferir:

```bash
curl -s https://api.github.com/repos/<owner>/vehicle-sales-service | jq '.id'        # <repo_id>
curl -s https://api.github.com/users/<owner> | jq '.id'                              # <owner_id>
```

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

**Também vale para `INTERNAL_API_TOKEN`:** é o token comparado em tempo constante nas chamadas
internas entre serviços (`X-Internal-Token`); precisa ser **byte-idêntico** ao valor configurado no
Core — qualquer divergência (um espaço a mais, um caractere trocado) faz **toda** chamada interna
retornar 401, dos dois lados. `PAYMENT_WEBHOOK_TOKEN` valida o header `X-Webhook-Token` do webhook de
pagamento voltado para a internet (`POST /webhooks/v1/payments`) e **nunca deve compartilhar valor
com `INTERNAL_API_TOKEN`**: são superfícies de ataque diferentes — o webhook é exposto publicamente
(provedor de pagamento externo), o token interno não é. Reaproveitar o mesmo segredo para os dois
faria um vazamento do webhook (mais exposto) comprometer também a comunicação interna entre serviços.

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

Atenção especial a três casos que não são óbvios lendo o Terraform:

1. **Permissões que a AWS exige do *chamador* por efeitos colaterais de serviço.** Não existe nenhum
   `aws_secretsmanager_secret` neste código, e ainda assim `secretsmanager:CreateSecret` é
   obrigatória: `manage_master_user_password = true` faz o RDS criar o segredo usando as permissões
   de quem chamou. Ler o `.tf` nunca revelaria isso — só a doc do serviço.
2. **Data source que busca por atributo faz `List` antes do `Get`.** O
   `data "aws_iam_openid_connect_provider" "github"` localiza o provider pela **URL**, não pelo ARN,
   então o provider Terraform chama `iam:ListOpenIDConnectProviders` para resolver URL → ARN e só
   depois `iam:GetOpenIDConnectProvider`. Conceder apenas o `Get` derruba o **`plan`** com
   `AccessDenied ... is not authorized to perform: iam:ListOpenIDConnectProviders`. Pior: `List` não
   aceita escopo por recurso, exige `Resource: "*"`, então precisa de statement próprio
   (`ListOidcProvidersToResolveUrl`). A regra vale para qualquer data source que faça lookup por
   atributo — nos demais isso passa despercebido só porque estão cobertos por wildcards como
   `ec2:Describe*`.
3. **Remoções.** Adicionar permissão em excesso falha silenciosamente para o lado seguro; **remover**
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

## Referências

- [README raiz](../README.md) — visão geral do serviço, arquitetura de código e execução local.
- [`infra/local/README.md`](./local/README.md) — validação local da infraestrutura com o Floci.
- `vehicle-core-service/infra/README.md` — infraestrutura do outro serviço da plataforma: dono do
  provider OIDC compartilhado, histórico completo dos incidentes de propagação de tags do KMS, e o
  formato real do `sub` do OIDC do GitHub Actions.
