from src.application.dtos import SoldVehicleResponse
from src.domain.repositories import SaleRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class ListSoldVehicles:
    """Caso de uso para listar os veículos vendidos, ordenados pelo preço de venda."""

    def __init__(self, sale_repository: SaleRepository) -> None:
        self._sale_repository = sale_repository

    async def execute(self) -> list[SoldVehicleResponse]:
        """
        Lista as vendas confirmadas em ordem crescente de preço de venda.

        Returns:
            Lista de DTOs de veículos vendidos com os dados comerciais da venda.
        """
        sold = await self._sale_repository.list_confirmed_by_price()
        logger.info("veiculos_vendidos_listados", total=len(sold))
        return [
            SoldVehicleResponse(
                sale_id=sale.id,
                vehicle_id=sale.vehicle_id,
                brand=replica.brand,
                model=replica.model,
                year=replica.year,
                color=replica.color,
                sale_price=sale.sale_price,
                buyer_cpf=sale.buyer_cpf,
                sale_date=sale.sale_date,
            )
            for sale, replica in sold
        ]
