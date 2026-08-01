import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities import Sale, SaleStatus, VehicleReplica
from src.interface.gateways.sale_gateway import SQLAlchemySaleRepository
from src.interface.gateways.vehicle_replica_gateway import SQLAlchemyVehicleReplicaRepository

VALID_CPF = "52998224725"


def _make_replica(vehicle_id: uuid.UUID) -> VehicleReplica:
    """
    Constrói uma réplica de veículo de exemplo para satisfazer a FK de sales.vehicle_id.

    Args:
        vehicle_id: Identificador do veículo.

    Returns:
        Instância de VehicleReplica pronta para o upsert.
    """
    return VehicleReplica(
        vehicle_id=vehicle_id,
        brand="Ford",
        model="Ka",
        year=2020,
        color="Vermelho",
        price=Decimal("60000.00"),
        version=1,
    )


def _make_sale(vehicle_id: uuid.UUID, payment_code: str) -> Sale:
    """
    Constrói uma venda de exemplo aguardando pagamento.

    Args:
        vehicle_id: Identificador do veículo comprado.
        payment_code: Código de pagamento único da venda.

    Returns:
        Instância de Sale pronta para persistência.
    """
    return Sale(
        vehicle_id=vehicle_id,
        buyer_cpf=VALID_CPF,
        sale_price=Decimal("60000.00"),
        payment_code=payment_code,
        sale_date=date(2026, 1, 12),
    )


async def _seed_replica(session_factory: async_sessionmaker[AsyncSession], vehicle_id: uuid.UUID) -> None:
    """
    Insere uma réplica de veículo, pré-requisito da FK sales.vehicle_id.

    Args:
        session_factory: Fábrica de sessões async do teste.
        vehicle_id: Identificador do veículo a inserir.
    """
    async with session_factory() as session:
        repository = SQLAlchemyVehicleReplicaRepository(session)
        await repository.upsert_snapshot(_make_replica(vehicle_id))
        await session.commit()


@pytest.mark.integration
class TestSaleGatewayTransitionStatus:
    """Integration tests for the conditional transition_status() against a real PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_transition_status_returns_none_on_from_status_mismatch(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that transition_status returns None (idempotency anchor) when the current status does not match."""
        # Arrange
        vehicle_id = uuid.uuid4()
        await _seed_replica(db_session_factory, vehicle_id)
        payment_code = f"pay-{vehicle_id}"
        async with db_session_factory() as setup_session:
            repository = SQLAlchemySaleRepository(setup_session)
            await repository.add(_make_sale(vehicle_id, payment_code))
            await setup_session.commit()
        async with db_session_factory() as first_session:
            first_repository = SQLAlchemySaleRepository(first_session)
            confirmed = await first_repository.transition_status(
                payment_code, SaleStatus.PENDING_PAYMENT, SaleStatus.CONFIRMED
            )
            await first_session.commit()
        assert confirmed is not None

        # Act: repeating the same conditional transition against the now-CONFIRMED sale
        async with db_session_factory() as second_session:
            second_repository = SQLAlchemySaleRepository(second_session)
            result = await second_repository.transition_status(
                payment_code, SaleStatus.PENDING_PAYMENT, SaleStatus.CONFIRMED
            )
            await second_session.commit()

        # Assert
        assert result is None


@pytest.mark.integration
class TestSaleGatewayPartialUniqueIndex:
    """Integration tests for the partial unique index guarding a single active sale per vehicle."""

    @pytest.mark.asyncio
    async def test_second_active_sale_for_same_vehicle_is_rejected(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that inserting a second PENDING_PAYMENT/CONFIRMED sale for the same vehicle raises IntegrityError."""
        # Arrange
        vehicle_id = uuid.uuid4()
        await _seed_replica(db_session_factory, vehicle_id)
        async with db_session_factory() as first_session:
            first_repository = SQLAlchemySaleRepository(first_session)
            await first_repository.add(_make_sale(vehicle_id, f"pay-a-{vehicle_id}"))
            await first_session.commit()

        # Act / Assert
        async with db_session_factory() as second_session:
            second_repository = SQLAlchemySaleRepository(second_session)
            with pytest.raises(IntegrityError):
                await second_repository.add(_make_sale(vehicle_id, f"pay-b-{vehicle_id}"))
