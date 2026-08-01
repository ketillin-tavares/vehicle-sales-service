import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities import VehicleReplica, VehicleStatus
from src.interface.gateways.vehicle_replica_gateway import SQLAlchemyVehicleReplicaRepository


def _make_replica(vehicle_id: uuid.UUID, version: int = 1, price: Decimal = Decimal("80000.00")) -> VehicleReplica:
    """
    Constrói uma réplica de veículo de exemplo para os testes de integração.

    Args:
        vehicle_id: Identificador do veículo.
        version: Versão do catálogo aplicada.
        price: Preço de catálogo do veículo.

    Returns:
        Instância de VehicleReplica pronta para o upsert.
    """
    return VehicleReplica(
        vehicle_id=vehicle_id,
        brand="Toyota",
        model="Hilux",
        year=2022,
        color="Preto",
        price=price,
        version=version,
    )


async def _reserve_and_commit(session_factory: async_sessionmaker[AsyncSession], vehicle_id: uuid.UUID) -> bool:
    """
    Reserva o veículo numa sessão dedicada, comitando o resultado.

    Args:
        session_factory: Fábrica de sessões async do teste.
        vehicle_id: Identificador do veículo a reservar.

    Returns:
        True se a reserva foi obtida por esta sessão; False caso contrário.
    """
    async with session_factory() as session:
        repository = SQLAlchemyVehicleReplicaRepository(session)
        reserved = await repository.reserve(vehicle_id)
        await session.commit()
        return reserved


@pytest.mark.integration
class TestVehicleReplicaGatewayReserveConcurrency:
    """Integration tests for the atomic conditional reserve() against a real PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_two_concurrent_reserves_only_one_wins(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that under two concurrent reserve attempts on the same vehicle, exactly one succeeds."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as setup_session:
            repository = SQLAlchemyVehicleReplicaRepository(setup_session)
            await repository.upsert_snapshot(_make_replica(vehicle_id))
            await setup_session.commit()

        # Act
        results = await asyncio.gather(
            _reserve_and_commit(db_session_factory, vehicle_id),
            _reserve_and_commit(db_session_factory, vehicle_id),
        )

        # Assert
        assert sorted(results) == [False, True]
        async with db_session_factory() as check_session:
            repository = SQLAlchemyVehicleReplicaRepository(check_session)
            final = await repository.get_by_id(vehicle_id)
        assert final is not None
        assert final.status is VehicleStatus.RESERVED

    @pytest.mark.asyncio
    async def test_reserve_returns_false_when_already_reserved(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that reserve() returns False when the vehicle is already RESERVED."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as setup_session:
            repository = SQLAlchemyVehicleReplicaRepository(setup_session)
            await repository.upsert_snapshot(_make_replica(vehicle_id))
            await setup_session.commit()
        first_result = await _reserve_and_commit(db_session_factory, vehicle_id)

        # Act
        second_result = await _reserve_and_commit(db_session_factory, vehicle_id)

        # Assert
        assert first_result is True
        assert second_result is False


@pytest.mark.integration
class TestVehicleReplicaGatewayUpsertSnapshot:
    """Integration tests for the version-guarded, status-preserving upsert against a real PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_upsert_skips_stale_version_and_never_overwrites_status(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that a stale-version snapshot is discarded and a newer one never overwrites the RESERVED status."""
        # Arrange
        vehicle_id = uuid.uuid4()
        async with db_session_factory() as setup_session:
            repository = SQLAlchemyVehicleReplicaRepository(setup_session)
            await repository.upsert_snapshot(_make_replica(vehicle_id, version=1, price=Decimal("80000.00")))
            await repository.reserve(vehicle_id)
            await setup_session.commit()

        # Act: stale snapshot (same version) must be discarded
        async with db_session_factory() as stale_session:
            stale_repository = SQLAlchemyVehicleReplicaRepository(stale_session)
            stale_applied = await stale_repository.upsert_snapshot(
                _make_replica(vehicle_id, version=1, price=Decimal("99999.00"))
            )
            await stale_session.commit()

        # Assert: discarded, status untouched
        async with db_session_factory() as check_session:
            check_repository = SQLAlchemyVehicleReplicaRepository(check_session)
            after_stale = await check_repository.get_by_id(vehicle_id)
        assert stale_applied is False
        assert after_stale is not None
        assert after_stale.status is VehicleStatus.RESERVED
        assert after_stale.price == Decimal("80000.00")

        # Act: newer snapshot must be applied but must never touch status
        async with db_session_factory() as fresh_session:
            fresh_repository = SQLAlchemyVehicleReplicaRepository(fresh_session)
            fresh_applied = await fresh_repository.upsert_snapshot(
                _make_replica(vehicle_id, version=2, price=Decimal("85000.00"))
            )
            await fresh_session.commit()

        # Assert: applied, catalog updated, status still RESERVED
        async with db_session_factory() as final_session:
            final_repository = SQLAlchemyVehicleReplicaRepository(final_session)
            after_fresh = await final_repository.get_by_id(vehicle_id)
        assert fresh_applied is True
        assert after_fresh is not None
        assert after_fresh.status is VehicleStatus.RESERVED
        assert after_fresh.price == Decimal("85000.00")
        assert after_fresh.version == 2
