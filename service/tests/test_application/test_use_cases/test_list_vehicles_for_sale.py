import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.list_vehicles_for_sale import ListVehiclesForSale
from src.domain.entities import VehicleReplica
from src.domain.repositories import VehicleReplicaRepository


def _make_replica(price: Decimal) -> VehicleReplica:
    """
    Constrói uma réplica de veículo de exemplo com o preço informado.

    Args:
        price: Preço de catálogo do veículo.

    Returns:
        Instância de VehicleReplica pronta para uso nos testes.
    """
    return VehicleReplica(
        vehicle_id=uuid.uuid4(),
        brand="Honda",
        model="Civic",
        year=2020,
        color="Preto",
        price=price,
        version=1,
    )


class TestListVehiclesForSale:
    """Tests for the ListVehiclesForSale use case."""

    @pytest.mark.asyncio
    async def test_execute_maps_and_preserves_repository_ordering(
        self, mock_vehicle_replica_repository: VehicleReplicaRepository
    ) -> None:
        """Test that execute maps each replica to a VehicleListingResponse preserving repository order."""
        # Arrange
        cheap = _make_replica(Decimal("50000.00"))
        expensive = _make_replica(Decimal("120000.00"))
        mock_vehicle_replica_repository.list_available_by_price = AsyncMock(return_value=[cheap, expensive])
        use_case = ListVehiclesForSale(vehicle_replica_repository=mock_vehicle_replica_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert [item.vehicle_id for item in result] == [cheap.vehicle_id, expensive.vehicle_id]
        assert result[0].price == Decimal("50000.00")
        assert result[1].price == Decimal("120000.00")

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list_when_no_vehicles_available(
        self, mock_vehicle_replica_repository: VehicleReplicaRepository
    ) -> None:
        """Test that execute returns an empty list when the repository has no available vehicles."""
        # Arrange
        mock_vehicle_replica_repository.list_available_by_price = AsyncMock(return_value=[])
        use_case = ListVehiclesForSale(vehicle_replica_repository=mock_vehicle_replica_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert result == []
