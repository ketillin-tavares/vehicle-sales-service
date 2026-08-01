import uuid
from decimal import Decimal

import pytest

from src.domain.entities.vehicle_replica import VehicleReplica, VehicleStatus
from src.domain.exceptions import VehicleUnavailableError


def _make_replica(status: VehicleStatus = VehicleStatus.AVAILABLE) -> VehicleReplica:
    """
    Constrói uma réplica de veículo de exemplo com o status informado.

    Args:
        status: Status comercial inicial da réplica.

    Returns:
        Instância de VehicleReplica pronta para uso nos testes.
    """
    return VehicleReplica(
        vehicle_id=uuid.uuid4(),
        brand="Fiat",
        model="Argo",
        year=2021,
        color="Branco",
        price=Decimal("70000.00"),
        status=status,
        version=1,
    )


class TestVehicleReplicaReserve:
    """Tests for the VehicleReplica.reserve() state transition."""

    def test_reserve_available_vehicle_transitions_to_reserved(self) -> None:
        """Test that reserving an AVAILABLE vehicle moves it to RESERVED and bumps updated_at."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.AVAILABLE)
        previous_updated_at = replica.updated_at

        # Act
        replica.reserve()

        # Assert
        assert replica.status is VehicleStatus.RESERVED
        assert replica.updated_at >= previous_updated_at

    def test_reserve_already_reserved_vehicle_raises(self) -> None:
        """Test that reserving a RESERVED vehicle raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.RESERVED)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.reserve()

    def test_reserve_sold_vehicle_raises(self) -> None:
        """Test that reserving a SOLD vehicle raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.SOLD)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.reserve()


class TestVehicleReplicaMarkSold:
    """Tests for the VehicleReplica.mark_sold() state transition."""

    def test_mark_sold_reserved_vehicle_transitions_to_sold(self) -> None:
        """Test that marking a RESERVED vehicle as sold moves it to SOLD and bumps updated_at."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.RESERVED)
        previous_updated_at = replica.updated_at

        # Act
        replica.mark_sold()

        # Assert
        assert replica.status is VehicleStatus.SOLD
        assert replica.updated_at >= previous_updated_at

    def test_mark_sold_available_vehicle_raises(self) -> None:
        """Test that marking an AVAILABLE vehicle as sold raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.AVAILABLE)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.mark_sold()

    def test_mark_sold_already_sold_vehicle_raises(self) -> None:
        """Test that marking an already SOLD vehicle as sold again raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.SOLD)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.mark_sold()


class TestVehicleReplicaRelease:
    """Tests for the VehicleReplica.release() state transition."""

    def test_release_reserved_vehicle_transitions_to_available(self) -> None:
        """Test that releasing a RESERVED vehicle moves it back to AVAILABLE and bumps updated_at."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.RESERVED)
        previous_updated_at = replica.updated_at

        # Act
        replica.release()

        # Assert
        assert replica.status is VehicleStatus.AVAILABLE
        assert replica.updated_at >= previous_updated_at

    def test_release_available_vehicle_raises(self) -> None:
        """Test that releasing an AVAILABLE vehicle raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.AVAILABLE)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.release()

    def test_release_sold_vehicle_raises(self) -> None:
        """Test that releasing a SOLD vehicle raises VehicleUnavailableError."""
        # Arrange
        replica = _make_replica(status=VehicleStatus.SOLD)

        # Act / Assert
        with pytest.raises(VehicleUnavailableError):
            replica.release()
