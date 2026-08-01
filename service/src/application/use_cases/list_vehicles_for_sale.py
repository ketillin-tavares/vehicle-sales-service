from src.application.dtos import VehicleListingResponse
from src.domain.repositories import VehicleReplicaRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class ListVehiclesForSale:
    """Caso de uso para listar os veículos disponíveis para venda, ordenados por preço."""

    def __init__(self, vehicle_replica_repository: VehicleReplicaRepository) -> None:
        self._vehicle_replica_repository = vehicle_replica_repository

    async def execute(self) -> list[VehicleListingResponse]:
        """
        Lista os veículos com status AVAILABLE em ordem crescente de preço.

        Returns:
            Lista de DTOs de veículos disponíveis para venda.
        """
        replicas = await self._vehicle_replica_repository.list_available_by_price()
        logger.info("veiculos_a_venda_listados", total=len(replicas))
        return [
            VehicleListingResponse(
                vehicle_id=replica.vehicle_id,
                brand=replica.brand,
                model=replica.model,
                year=replica.year,
                color=replica.color,
                price=replica.price,
            )
            for replica in replicas
        ]
