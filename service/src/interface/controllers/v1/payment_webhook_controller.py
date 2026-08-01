from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import PaymentWebhookResponse
from src.application.ports import CoreNotifier
from src.application.use_cases import ProcessPaymentWebhook
from src.domain.entities import SaleStatus, VehicleStatus
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_core_notifier, verify_webhook_token
from src.interface.gateways import SQLAlchemySaleRepository, SQLAlchemyVehicleReplicaRepository
from src.interface.presenters import ConflictResponse, NotFoundResponse, PaymentWebhookRequest, UnauthorizedResponse

router = APIRouter(prefix="/webhooks/v1", tags=["webhooks"])

VEHICLE_STATUS_BY_SALE_STATUS: dict[SaleStatus, VehicleStatus] = {
    SaleStatus.CONFIRMED: VehicleStatus.SOLD,
    SaleStatus.CANCELED: VehicleStatus.AVAILABLE,
}


@router.post(
    "/payments",
    response_model=PaymentWebhookResponse,
    dependencies=[Depends(verify_webhook_token)],
    responses={
        401: {"model": UnauthorizedResponse},
        404: {"model": NotFoundResponse},
        409: {"model": ConflictResponse},
    },
)
async def process_payment_webhook(
    request: PaymentWebhookRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    core_notifier: CoreNotifier = Depends(get_core_notifier),
) -> PaymentWebhookResponse:
    """
    Processa a notificação de pagamento da entidade externa, de forma idempotente.

    A notificação de status ao Core é agendada como background task, executada após o commit
    da sessão e o envio da resposta (best-effort).

    Args:
        request: Código de pagamento e status notificado.
        background_tasks: Coletor de tarefas executadas após a resposta.
        session: Sessão de banco fornecida pela dependência de infraestrutura.
        core_notifier: Port de notificação do vehicle-core-service.

    Returns:
        DTO com o status resultante da venda.
    """
    use_case = ProcessPaymentWebhook(
        sale_repository=SQLAlchemySaleRepository(session),
        vehicle_replica_repository=SQLAlchemyVehicleReplicaRepository(session),
    )
    result = await use_case.execute(payment_code=request.payment_code, notification=request.status)
    background_tasks.add_task(
        core_notifier.notify_status,
        result.vehicle_id,
        VEHICLE_STATUS_BY_SALE_STATUS[result.status],
    )
    return result
