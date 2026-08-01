from src.application.dtos import PaymentNotificationStatus, PaymentWebhookResponse
from src.domain.entities import SaleStatus, VehicleStatus
from src.domain.exceptions import InvalidPaymentTransitionError, SaleNotFoundError
from src.domain.repositories import SaleRepository, VehicleReplicaRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()

TRANSITIONS: dict[PaymentNotificationStatus, tuple[SaleStatus, VehicleStatus]] = {
    PaymentNotificationStatus.PAID: (SaleStatus.CONFIRMED, VehicleStatus.SOLD),
    PaymentNotificationStatus.CANCELED: (SaleStatus.CANCELED, VehicleStatus.AVAILABLE),
}


class ProcessPaymentWebhook:
    """Caso de uso para processar a notificação de pagamento da entidade externa."""

    def __init__(
        self,
        sale_repository: SaleRepository,
        vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        self._sale_repository = sale_repository
        self._vehicle_replica_repository = vehicle_replica_repository

    async def execute(self, payment_code: str, notification: PaymentNotificationStatus) -> PaymentWebhookResponse:
        """
        Aplica a notificação de pagamento à venda e ao status do veículo.

        A transição é condicional e atômica; notificações repetidas para um status já aplicado
        são idempotentes e não alteram estado.

        Args:
            payment_code: Código de pagamento informado pela entidade de pagamento.
            notification: Status externo notificado (`paid` ou `canceled`).

        Returns:
            DTO com o código de pagamento, o veículo e o status resultante da venda.

        Raises:
            SaleNotFoundError: Se não existe venda para o código informado.
            InvalidPaymentTransitionError: Se a venda já está em um status final conflitante.
        """
        target_sale_status, target_vehicle_status = TRANSITIONS[notification]

        sale = await self._sale_repository.transition_status(
            payment_code,
            SaleStatus.PENDING_PAYMENT,
            target_sale_status,
        )
        if sale is None:
            return await self._resolve_without_transition(payment_code, target_sale_status)

        await self._vehicle_replica_repository.set_status(sale.vehicle_id, target_vehicle_status)
        logger.info(
            "webhook_pagamento_aplicado",
            payment_code=payment_code,
            sale_status=sale.status,
            vehicle_status=target_vehicle_status,
        )
        return PaymentWebhookResponse(payment_code=payment_code, vehicle_id=sale.vehicle_id, status=sale.status)

    async def _resolve_without_transition(
        self,
        payment_code: str,
        target_sale_status: SaleStatus,
    ) -> PaymentWebhookResponse:
        """
        Decide o desfecho quando a transição condicional não foi aplicada.

        Args:
            payment_code: Código de pagamento informado.
            target_sale_status: Status que a notificação pretendia aplicar.

        Returns:
            DTO com o status atual da venda quando a notificação é uma repetição idempotente.

        Raises:
            SaleNotFoundError: Se não existe venda para o código informado.
            InvalidPaymentTransitionError: Se a venda está em um status final conflitante.
        """
        sale = await self._sale_repository.get_by_payment_code(payment_code)
        if sale is None:
            logger.info("webhook_pagamento_venda_inexistente", payment_code=payment_code)
            raise SaleNotFoundError(f"Venda não encontrada para o código de pagamento {payment_code}")

        if sale.status is target_sale_status:
            logger.info("webhook_pagamento_idempotente", payment_code=payment_code, sale_status=sale.status)
            return PaymentWebhookResponse(payment_code=payment_code, vehicle_id=sale.vehicle_id, status=sale.status)

        logger.warning(
            "webhook_pagamento_transicao_invalida",
            payment_code=payment_code,
            sale_status=sale.status,
            target_status=target_sale_status,
        )
        raise InvalidPaymentTransitionError(
            f"Venda {payment_code} está em {sale.status} e não pode transicionar para {target_sale_status}"
        )
