import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.application.dtos import VehicleSnapshot
from src.application.use_cases.upsert_vehicle_replica import UpsertVehicleReplica
from src.domain.repositories import VehicleReplicaRepository


def _make_snapshot(vehicle_id: uuid.UUID, version: int) -> VehicleSnapshot:
    """
    Constrói um snapshot de catálogo de exemplo com a versão informada.

    Args:
        vehicle_id: Identificador do veículo sincronizado.
        version: Versão do catálogo no Core.

    Returns:
        Instância de VehicleSnapshot pronta para uso nos testes.
    """
    return VehicleSnapshot(
        vehicle_id=vehicle_id,
        brand="Volkswagen",
        model="Gol",
        year=2018,
        color="Azul",
        price=Decimal("45000.00"),
        version=version,
    )


class TestUpsertVehicleReplica:
    """Tests for the UpsertVehicleReplica use case."""

    @pytest.mark.asyncio
    async def test_execute_returns_true_when_snapshot_applied(
        self, vehicle_id: uuid.UUID, mock_vehicle_replica_repository: VehicleReplicaRepository
    ) -> None:
        """Test that execute returns True when the repository applies the snapshot."""
        # Arrange
        mock_vehicle_replica_repository.upsert_snapshot = AsyncMock(return_value=True)
        snapshot = _make_snapshot(vehicle_id, version=2)
        use_case = UpsertVehicleReplica(vehicle_replica_repository=mock_vehicle_replica_repository)

        # Act
        applied = await use_case.execute(snapshot)

        # Assert
        assert applied is True
        mock_vehicle_replica_repository.upsert_snapshot.assert_awaited_once()
        persisted_replica = mock_vehicle_replica_repository.upsert_snapshot.call_args.args[0]
        assert persisted_replica.vehicle_id == vehicle_id
        assert persisted_replica.version == 2

    @pytest.mark.asyncio
    async def test_execute_returns_false_when_snapshot_is_stale(
        self, vehicle_id: uuid.UUID, mock_vehicle_replica_repository: VehicleReplicaRepository
    ) -> None:
        """Test that execute returns False when the repository discards a stale-version snapshot."""
        # Arrange
        mock_vehicle_replica_repository.upsert_snapshot = AsyncMock(return_value=False)
        snapshot = _make_snapshot(vehicle_id, version=1)
        use_case = UpsertVehicleReplica(vehicle_replica_repository=mock_vehicle_replica_repository)

        # Act
        applied = await use_case.execute(snapshot)

        # Assert
        assert applied is False
