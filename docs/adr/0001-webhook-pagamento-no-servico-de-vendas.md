# ADR-0001: Webhook de pagamento hospedado no vehicle-sales-service

**Status:** Aceito
**Data:** 2026-08-01
**Autor:** Equipe de Arquitetura
**Contexto:** vehicle-sales-service MVP (desafio estudantil)

---

## Contexto

O enunciado do desafio lista a necessidade de um webhook de notificação de pagamento (código de
pagamento → status `paid`/`canceled`) entre as necessidades gerais da plataforma, mas **não o
atribui explicitamente a nenhum dos dois serviços**. A única atribuição explícita e inequívoca do
enunciado é: "endpoints de listagem e de compra isolados no serviço de vendas".

Era preciso decidir em qual serviço — `vehicle-core-service` (cadastro/edição do catálogo) ou
`vehicle-sales-service` (venda/listagem) — o webhook deveria viver, dado que os dois têm bancos de
dados segregados e se comunicam apenas via HTTP.

---

## Decisão

O webhook de pagamento foi implementado no **vehicle-sales-service**, em
`POST /webhooks/v1/payments`, protegido pelo header `X-Webhook-Token` (comparado em tempo
constante contra o token configurado), com processamento **idempotente**.

Motivos:

1. **Dados do ciclo de vida da venda vivem no banco do serviço de vendas.** O `payment_code` e a
   transição de status da venda (`PENDING_PAYMENT` → `CONFIRMED`/`CANCELED`) pertencem ao banco
   segregado do `vehicle-sales-service`. O webhook é a conclusão do fluxo de compra — fluxo que o
   próprio enunciado manda isolar no serviço de vendas.
2. **Evita acoplamento síncrono desnecessário entre os serviços.** Se o webhook vivesse no
   `vehicle-core-service`, concluir uma compra passaria a depender do Core estar no ar e de uma
   chamada síncrona Core → Sales só para localizar a venda pelo código de pagamento — exatamente o
   acoplamento que o requisito de isolamento de bancos e responsabilidades busca evitar.
3. **A transição precisa ser atômica com a mudança de status do veículo.** A confirmação da venda
   (`SaleStatus.CONFIRMED`) e a marcação do veículo como vendido só podem ser garantidas na mesma
   transação dentro do banco de vendas; hospedar o webhook em outro serviço tornaria essa
   atomicidade impossível ou exigiria um mecanismo de compensação distribuído, fora de escopo para
   o MVP.

### Alternativa rejeitada

Um **endpoint proxy no `vehicle-core-service`** que apenas repassasse a notificação para o
`vehicle-sales-service` foi considerado. Ele atenderia à letra do enunciado (webhook "no Core"),
mas ao custo de acoplamento e latência adicionais, sem nenhum ganho real — o processamento
efetivo (buscar a venda, aplicar a transição, marcar o veículo) continuaria precisando ocorrer no
serviço de vendas. A alternativa foi descartada por não resolver nenhum problema real.

---

## Consequências

- O `vehicle-core-service` nunca recebe diretamente a notificação de pagamento; ele é informado do
  novo status comercial do veículo de forma assíncrona, via `PATCH
  /internal/v1/vehicles/{vehicle_id}/status`, chamado pelo `vehicle-sales-service` como background
  task após o commit do webhook (best-effort).
- O `vehicle-sales-service` é o único serviço com conhecimento do `payment_code` e do ciclo de vida
  da venda — coerente com a segregação de bancos de dados exigida pelo enunciado.
- Notificações repetidas para um mesmo `payment_code` e status já aplicado são idempotentes (não
  alteram estado); notificações que tentam aplicar uma transição conflitante com o status atual da
  venda são rejeitadas.

---

## Implementação

- **Controller:** `src/interface/controllers/v1/payment_webhook_controller.py`
  (`POST /webhooks/v1/payments`).
- **Autenticação:** header `X-Webhook-Token`, validado em
  `src/interface/controllers/dependencies.py` (`verify_webhook_token`).
- **Caso de uso:** `src/application/use_cases/process_payment_webhook.py`
  (`ProcessPaymentWebhook`), com transição condicional e atômica no repositório de vendas.
- **Notificação ao Core:** `CoreNotifier` (port) via background task, após o commit da sessão.
- **Testes:** unitários do caso de uso e do controller, cobrindo os cenários `paid`, `canceled`,
  notificação duplicada (idempotência) e transição conflitante (venda em status final divergente).
