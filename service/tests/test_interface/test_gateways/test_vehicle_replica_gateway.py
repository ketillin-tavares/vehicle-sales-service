import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import VehicleReplica, VehicleStatus
from src.infrastructure.models import VehicleReplicaModel
from src.interface.gateways.vehicle_replica_gateway import (
    SQLAlchemyVehicleReplicaRepository,
    map_replica_model_to_entity,
)


def _make_model(vehicle_id: uuid.UUID, status: str = "AVAILABLE", version: int = 1) -> VehicleReplicaModel:
    """
    Constrói um VehicleReplicaModel de exemplo sem tocar o banco de dados.

    Args:
        vehicle_id: Identificador do veículo.
        status: Status comercial persistido.
        version: Versão do catálogo aplicada.

    Returns:
        Instância ORM pronta para uso nos testes.
    """
    now = datetime.now(UTC)
    return VehicleReplicaModel(
        vehicle_id=vehicle_id,
        brand="Renault",
        model="Kwid",
        year=2021,
        color="Laranja",
        price=Decimal("55000.00"),
        status=status,
        version=version,
        synced_at=now,
        created_at=now,
        updated_at=now,
    )


class TestMapReplicaModelToEntity:
    """Tests for the map_replica_model_to_entity translation function."""

    def test_maps_all_fields_from_model_to_entity(self, vehicle_id: uuid.UUID) -> None:
        """Test that the mapper translates every ORM field to the equivalent domain entity field."""
        # Arrange
        model = _make_model(vehicle_id, status="RESERVED", version=3)

        # Act
        entity = map_replica_model_to_entity(model)

        # Assert
        assert isinstance(entity, VehicleReplica)
        assert entity.vehicle_id == vehicle_id
        assert entity.status is VehicleStatus.RESERVED
        assert entity.version == 3
        assert entity.brand == model.brand


class TestSQLAlchemyVehicleReplicaRepositoryGetById:
    """Tests for SQLAlchemyVehicleReplicaRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_entity_when_found(self, vehicle_id: uuid.UUID) -> None:
        """Test that get_by_id maps the ORM model to a VehicleReplica when found."""
        # Arrange
        model = _make_model(vehicle_id)
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        entity = await repository.get_by_id(vehicle_id)

        # Assert
        assert entity is not None
        assert entity.vehicle_id == vehicle_id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_missing(self, vehicle_id: uuid.UUID) -> None:
        """Test that get_by_id returns None when no matching row exists."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        entity = await repository.get_by_id(vehicle_id)

        # Assert
        assert entity is None


class TestSQLAlchemyVehicleReplicaRepositoryListAvailableByPrice:
    """Tests for SQLAlchemyVehicleReplicaRepository.list_available_by_price()."""

    @pytest.mark.asyncio
    async def test_list_available_by_price_maps_every_row(self, vehicle_id: uuid.UUID) -> None:
        """Test that list_available_by_price maps every returned row to a VehicleReplica entity."""
        # Arrange
        models = [_make_model(vehicle_id), _make_model(uuid.uuid4())]
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = models
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        entities = await repository.list_available_by_price()

        # Assert
        assert len(entities) == 2
        assert all(isinstance(entity, VehicleReplica) for entity in entities)


class TestSQLAlchemyVehicleReplicaRepositoryReserve:
    """Tests for SQLAlchemyVehicleReplicaRepository.reserve()."""

    @pytest.mark.asyncio
    async def test_reserve_returns_true_when_row_updated(self, vehicle_id: uuid.UUID) -> None:
        """Test that reserve returns True when the conditional UPDATE affects exactly one row."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        reserved = await repository.reserve(vehicle_id)

        # Assert
        assert reserved is True

    @pytest.mark.asyncio
    async def test_reserve_returns_false_when_no_row_updated(self, vehicle_id: uuid.UUID) -> None:
        """Test that reserve returns False when the conditional UPDATE affects zero rows."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        reserved = await repository.reserve(vehicle_id)

        # Assert
        assert reserved is False


class TestSQLAlchemyVehicleReplicaRepositorySetStatus:
    """Tests for SQLAlchemyVehicleReplicaRepository.set_status()."""

    @pytest.mark.asyncio
    async def test_set_status_executes_update_statement(self, vehicle_id: uuid.UUID) -> None:
        """Test that set_status issues exactly one UPDATE execution against the session."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        repository = SQLAlchemyVehicleReplicaRepository(session)

        # Act
        await repository.set_status(vehicle_id, VehicleStatus.SOLD)

        # Assert
        session.execute.assert_awaited_once()


class TestSQLAlchemyVehicleReplicaRepositoryUpsertSnapshot:
    """Tests for SQLAlchemyVehicleReplicaRepository.upsert_snapshot()."""

    @pytest.mark.asyncio
    async def test_upsert_snapshot_returns_true_when_applied(self, vehicle_id: uuid.UUID) -> None:
        """Test that upsert_snapshot returns True when the statement affects at least one row."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)
        replica = VehicleReplica(
            vehicle_id=vehicle_id,
            brand="Jeep",
            model="Renegade",
            year=2023,
            color="Verde",
            price=Decimal("130000.00"),
            version=2,
        )

        # Act
        applied = await repository.upsert_snapshot(replica)

        # Assert
        assert applied is True

    @pytest.mark.asyncio
    async def test_upsert_snapshot_returns_false_when_stale(self, vehicle_id: uuid.UUID) -> None:
        """Test that upsert_snapshot returns False when the version guard discards the snapshot."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result
        repository = SQLAlchemyVehicleReplicaRepository(session)
        replica = VehicleReplica(
            vehicle_id=vehicle_id,
            brand="Jeep",
            model="Renegade",
            year=2023,
            color="Verde",
            price=Decimal("130000.00"),
            version=1,
        )

        # Act
        applied = await repository.upsert_snapshot(replica)

        # Assert
        assert applied is False
