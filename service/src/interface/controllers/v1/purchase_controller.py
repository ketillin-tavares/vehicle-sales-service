from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import PurchaseResponse
from src.application.ports import CoreNotifier
from src.application.use_cases import PurchaseVehicle
from src.domain.entities import VehicleStatus
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_core_notifier
from src.interface.gateways import SQLAlchemySaleRepository, SQLAlchemyVehicleReplicaRepository
from src.interface.presenters import ConflictResponse, NotFoundResponse, PurchaseRequest

router = APIRouter(prefix="/purchases", tags=["v1"])


@router.post(
    "",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": NotFoundResponse}, 409: {"model": ConflictResponse}},
)
async def purchase_vehicle(
    request: PurchaseRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    core_notifier: CoreNotifier = Depends(get_core_notifier),
) -> PurchaseResponse:
    """
    Compra um veículo, reservando-o e criando a venda aguardando pagamento.

    A notificação de status ao Core é agendada como background task, executada após o commit
    da sessão e o envio da resposta (best-effort).

    Args:
        request: Dados da compra (veículo, CPF do comprador e data da venda).
        background_tasks: Coletor de tarefas executadas após a resposta.
        session: Sessão de banco fornecida pela dependência de infraestrutura.
        core_notifier: Port de notificação do vehicle-core-service.

    Returns:
        DTO com os dados da venda criada, incluindo o código de pagamento.
    """
    use_case = PurchaseVehicle(
        vehicle_replica_repository=SQLAlchemyVehicleReplicaRepository(session),
        sale_repository=SQLAlchemySaleRepository(session),
    )
    purchase = await use_case.execute(
        vehicle_id=request.vehicle_id,
        buyer_cpf=request.buyer_cpf,
        sale_date=request.sale_date,
    )
    background_tasks.add_task(core_notifier.notify_status, purchase.vehicle_id, VehicleStatus.RESERVED)
    return purchase
