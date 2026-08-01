import secrets
import uuid
from datetime import date

from src.application.dtos import PurchaseResponse
from src.domain.entities import Sale
from src.domain.exceptions import VehicleNotFoundError, VehicleUnavailableError
from src.domain.repositories import SaleRepository, VehicleReplicaRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()

PAYMENT_CODE_BYTES = 24


class PurchaseVehicle:
    """Caso de uso para comprar um veículo, reservando-o e criando a venda pendente de pagamento."""

    def __init__(
        self,
        vehicle_replica_repository: VehicleReplicaRepository,
        sale_repository: SaleRepository,
    ) -> None:
        self._vehicle_replica_repository = vehicle_replica_repository
        self._sale_repository = sale_repository

    async def execute(self, vehicle_id: uuid.UUID, buyer_cpf: str, sale_date: date) -> PurchaseResponse:
        """
        Reserva o veículo e registra a venda aguardando pagamento.

        Args:
            vehicle_id: Identificador do veículo desejado.
            buyer_cpf: CPF do comprador, somente dígitos.
            sale_date: Data da venda.

        Returns:
            DTO com os dados da venda criada, incluindo o código de pagamento.

        Raises:
            VehicleNotFoundError: Se o veículo não existe na réplica local.
            VehicleUnavailableError: Se o veículo não estava disponível para reserva.
            InvalidCpfError: Se o CPF do comprador é inválido.
        """
        replica = await self._vehicle_replica_repository.get_by_id(vehicle_id)
        if replica is None:
            logger.info("compra_veiculo_inexistente", vehicle_id=str(vehicle_id))
            raise VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")

        reserved = await self._vehicle_replica_repository.reserve(vehicle_id)
        if not reserved:
            logger.info("compra_veiculo_indisponivel", vehicle_id=str(vehicle_id))
            raise VehicleUnavailableError(f"Veículo {vehicle_id} não está disponível para compra")

        sale = Sale(
            vehicle_id=vehicle_id,
            buyer_cpf=buyer_cpf,
            sale_price=replica.price,
            payment_code=secrets.token_urlsafe(PAYMENT_CODE_BYTES),
            sale_date=sale_date,
        )
        created = await self._sale_repository.add(sale)

        logger.info(
            "compra_registrada",
            sale_id=str(created.id),
            vehicle_id=str(created.vehicle_id),
            payment_code=created.payment_code,
        )
        return PurchaseResponse(
            sale_id=created.id,
            vehicle_id=created.vehicle_id,
            sale_price=created.sale_price,
            payment_code=created.payment_code,
            status=created.status,
        )
