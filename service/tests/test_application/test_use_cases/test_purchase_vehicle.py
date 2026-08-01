import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.purchase_vehicle import PurchaseVehicle
from src.domain.entities import Sale, VehicleReplica
from src.domain.exceptions import VehicleNotFoundError, VehicleUnavailableError
from src.domain.repositories import SaleRepository, VehicleReplicaRepository

VALID_CPF = "52998224725"


class TestPurchaseVehicle:
    """Tests for the PurchaseVehicle use case."""

    @pytest.mark.asyncio
    async def test_execute_happy_path_reserves_and_creates_pending_sale(
        self,
        vehicle_id: uuid.UUID,
        sample_vehicle_replica: VehicleReplica,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
        mock_sale_repository: SaleRepository,
    ) -> None:
        """Test the purchase happy path: price frozen from the replica, non-empty payment_code, PENDING_PAYMENT."""
        # Arrange
        mock_vehicle_replica_repository.get_by_id = AsyncMock(return_value=sample_vehicle_replica)
        mock_vehicle_replica_repository.reserve = AsyncMock(return_value=True)
        mock_sale_repository.add = AsyncMock(side_effect=lambda sale: sale)
        use_case = PurchaseVehicle(
            vehicle_replica_repository=mock_vehicle_replica_repository,
            sale_repository=mock_sale_repository,
        )

        # Act
        result = await use_case.execute(vehicle_id=vehicle_id, buyer_cpf=VALID_CPF, sale_date=date(2026, 1, 20))

        # Assert
        assert result.vehicle_id == vehicle_id
        assert result.sale_price == sample_vehicle_replica.price
        assert result.payment_code
        assert result.status.value == "PENDING_PAYMENT"
        mock_vehicle_replica_repository.reserve.assert_awaited_once_with(vehicle_id)
        added_sale: Sale = mock_sale_repository.add.call_args.args[0]
        assert added_sale.buyer_cpf == VALID_CPF
        assert added_sale.sale_price == sample_vehicle_replica.price

    @pytest.mark.asyncio
    async def test_execute_generates_distinct_payment_codes_across_calls(
        self,
        vehicle_id: uuid.UUID,
        sample_vehicle_replica: VehicleReplica,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
        mock_sale_repository: SaleRepository,
    ) -> None:
        """Test that each purchase generates a distinct, non-empty payment_code."""
        # Arrange
        mock_vehicle_replica_repository.get_by_id = AsyncMock(return_value=sample_vehicle_replica)
        mock_vehicle_replica_repository.reserve = AsyncMock(return_value=True)
        mock_sale_repository.add = AsyncMock(side_effect=lambda sale: sale)
        use_case = PurchaseVehicle(
            vehicle_replica_repository=mock_vehicle_replica_repository,
            sale_repository=mock_sale_repository,
        )

        # Act
        first = await use_case.execute(vehicle_id=vehicle_id, buyer_cpf=VALID_CPF, sale_date=date(2026, 1, 20))
        second = await use_case.execute(vehicle_id=vehicle_id, buyer_cpf=VALID_CPF, sale_date=date(2026, 1, 20))

        # Assert
        assert first.payment_code != second.payment_code

    @pytest.mark.asyncio
    async def test_execute_raises_vehicle_not_found_when_replica_missing(
        self,
        vehicle_id: uuid.UUID,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
        mock_sale_repository: SaleRepository,
    ) -> None:
        """Test that execute raises VehicleNotFoundError when the vehicle replica does not exist."""
        # Arrange
        mock_vehicle_replica_repository.get_by_id = AsyncMock(return_value=None)
        use_case = PurchaseVehicle(
            vehicle_replica_repository=mock_vehicle_replica_repository,
            sale_repository=mock_sale_repository,
        )

        # Act / Assert
        with pytest.raises(VehicleNotFoundError):
            await use_case.execute(vehicle_id=vehicle_id, buyer_cpf=VALID_CPF, sale_date=date(2026, 1, 20))
        mock_sale_repository.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_raises_vehicle_unavailable_when_reserve_fails(
        self,
        vehicle_id: uuid.UUID,
        sample_vehicle_replica: VehicleReplica,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
        mock_sale_repository: SaleRepository,
    ) -> None:
        """Test that execute raises VehicleUnavailableError when the atomic reserve returns False."""
        # Arrange
        mock_vehicle_replica_repository.get_by_id = AsyncMock(return_value=sample_vehicle_replica)
        mock_vehicle_replica_repository.reserve = AsyncMock(return_value=False)
        use_case = PurchaseVehicle(
            vehicle_replica_repository=mock_vehicle_replica_repository,
            sale_repository=mock_sale_repository,
        )

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            await use_case.execute(vehicle_id=vehicle_id, buyer_cpf=VALID_CPF, sale_date=date(2026, 1, 20))
        mock_sale_repository.add.assert_not_called()
