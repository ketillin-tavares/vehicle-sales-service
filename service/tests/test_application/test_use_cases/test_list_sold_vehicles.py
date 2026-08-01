import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.list_sold_vehicles import ListSoldVehicles
from src.domain.entities import Sale, SaleStatus, VehicleReplica
from src.domain.repositories import SaleRepository

VALID_CPF = "52998224725"


def _make_sale_with_replica(sale_price: Decimal) -> tuple[Sale, VehicleReplica]:
    """
    Constrói um par (venda confirmada, réplica de veículo) com o preço de venda informado.

    Args:
        sale_price: Preço congelado de venda.

    Returns:
        Tupla (Sale, VehicleReplica) pronta para uso nos testes.
    """
    vehicle_id = uuid.uuid4()
    sale = Sale(
        vehicle_id=vehicle_id,
        buyer_cpf=VALID_CPF,
        sale_price=sale_price,
        payment_code=f"code-{vehicle_id}",
        status=SaleStatus.CONFIRMED,
        sale_date=date(2026, 1, 10),
    )
    replica = VehicleReplica(
        vehicle_id=vehicle_id,
        brand="Chevrolet",
        model="Onix",
        year=2019,
        color="Vermelho",
        price=sale_price,
        version=1,
    )
    return sale, replica


class TestListSoldVehicles:
    """Tests for the ListSoldVehicles use case."""

    @pytest.mark.asyncio
    async def test_execute_maps_and_preserves_repository_ordering(self, mock_sale_repository: SaleRepository) -> None:
        """Test that execute maps each (sale, replica) pair to a SoldVehicleResponse preserving order."""
        # Arrange
        cheap_pair = _make_sale_with_replica(Decimal("60000.00"))
        expensive_pair = _make_sale_with_replica(Decimal("150000.00"))
        mock_sale_repository.list_confirmed_by_price = AsyncMock(return_value=[cheap_pair, expensive_pair])
        use_case = ListSoldVehicles(sale_repository=mock_sale_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert [item.sale_id for item in result] == [cheap_pair[0].id, expensive_pair[0].id]
        assert result[0].sale_price == Decimal("60000.00")
        assert result[1].sale_price == Decimal("150000.00")
        assert result[0].buyer_cpf == VALID_CPF

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list_when_no_sales_confirmed(
        self, mock_sale_repository: SaleRepository
    ) -> None:
        """Test that execute returns an empty list when the repository has no confirmed sales."""
        # Arrange
        mock_sale_repository.list_confirmed_by_price = AsyncMock(return_value=[])
        use_case = ListSoldVehicles(sale_repository=mock_sale_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert result == []
