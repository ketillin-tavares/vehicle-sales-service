import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Sale, SaleStatus
from src.infrastructure.models import SaleModel, VehicleReplicaModel
from src.interface.gateways.sale_gateway import SQLAlchemySaleRepository

VALID_CPF = "52998224725"


def _make_sale_model(vehicle_id: uuid.UUID, status: str = "PENDING_PAYMENT") -> SaleModel:
    """
    Constrói um SaleModel de exemplo sem tocar o banco de dados.

    Args:
        vehicle_id: Identificador do veículo associado à venda.
        status: Status persistido da venda.

    Returns:
        Instância ORM pronta para uso nos testes.
    """
    now = datetime.now(UTC)
    return SaleModel(
        id=uuid.uuid4(),
        vehicle_id=vehicle_id,
        buyer_cpf=VALID_CPF,
        sale_price=Decimal("88000.00"),
        payment_code="pay-code",
        status=status,
        sale_date=date(2026, 1, 10),
        confirmed_at=None,
        canceled_at=None,
        created_at=now,
        updated_at=now,
    )


def _make_replica_model(vehicle_id: uuid.UUID) -> VehicleReplicaModel:
    """
    Constrói um VehicleReplicaModel de exemplo sem tocar o banco de dados.

    Args:
        vehicle_id: Identificador do veículo.

    Returns:
        Instância ORM pronta para uso nos testes.
    """
    now = datetime.now(UTC)
    return VehicleReplicaModel(
        vehicle_id=vehicle_id,
        brand="Hyundai",
        model="HB20",
        year=2021,
        color="Prata",
        price=Decimal("88000.00"),
        status="SOLD",
        version=1,
        synced_at=now,
        created_at=now,
        updated_at=now,
    )


class TestSQLAlchemySaleRepositoryAdd:
    """Tests for SQLAlchemySaleRepository.add()."""

    @pytest.mark.asyncio
    async def test_add_persists_sale_and_returns_entity(self, vehicle_id: uuid.UUID) -> None:
        """Test that add stages the ORM model in the session and returns the equivalent domain entity."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        repository = SQLAlchemySaleRepository(session)
        sale = Sale(
            vehicle_id=vehicle_id,
            buyer_cpf=VALID_CPF,
            sale_price=Decimal("88000.00"),
            payment_code="pay-code",
            sale_date=date(2026, 1, 10),
        )

        # Act
        created = await repository.add(sale)

        # Assert
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert created.vehicle_id == vehicle_id
        assert created.payment_code == "pay-code"


class TestSQLAlchemySaleRepositoryGetByPaymentCode:
    """Tests for SQLAlchemySaleRepository.get_by_payment_code()."""

    @pytest.mark.asyncio
    async def test_returns_entity_when_found(self, vehicle_id: uuid.UUID) -> None:
        """Test that get_by_payment_code maps the ORM model to a Sale when found."""
        # Arrange
        model = _make_sale_model(vehicle_id)
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        sale = await repository.get_by_payment_code("pay-code")

        # Assert
        assert sale is not None
        assert sale.payment_code == "pay-code"

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self) -> None:
        """Test that get_by_payment_code returns None when no matching row exists."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        sale = await repository.get_by_payment_code("unknown")

        # Assert
        assert sale is None


class TestSQLAlchemySaleRepositoryTransitionStatus:
    """Tests for SQLAlchemySaleRepository.transition_status()."""

    @pytest.mark.asyncio
    async def test_returns_updated_entity_when_transition_applied(self, vehicle_id: uuid.UUID) -> None:
        """Test that transition_status returns the updated Sale when the conditional UPDATE affects a row."""
        # Arrange
        model = _make_sale_model(vehicle_id, status="CONFIRMED")
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.one_or_none.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        sale = await repository.transition_status("pay-code", SaleStatus.PENDING_PAYMENT, SaleStatus.CONFIRMED)

        # Assert
        assert sale is not None
        assert sale.status is SaleStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_cancel_transition_sets_canceled_at(self, vehicle_id: uuid.UUID) -> None:
        """Test that transitioning to CANCELED returns a Sale reflecting the cancellation."""
        # Arrange
        model = _make_sale_model(vehicle_id, status="CANCELED")
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.one_or_none.return_value = model
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        sale = await repository.transition_status("pay-code", SaleStatus.PENDING_PAYMENT, SaleStatus.CANCELED)

        # Assert
        assert sale is not None
        assert sale.status is SaleStatus.CANCELED

    @pytest.mark.asyncio
    async def test_returns_none_when_current_status_does_not_match(self) -> None:
        """Test that transition_status returns None when the from_status guard does not match any row."""
        # Arrange
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.one_or_none.return_value = None
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        sale = await repository.transition_status("pay-code", SaleStatus.PENDING_PAYMENT, SaleStatus.CONFIRMED)

        # Assert
        assert sale is None


class TestSQLAlchemySaleRepositoryListConfirmedByPrice:
    """Tests for SQLAlchemySaleRepository.list_confirmed_by_price()."""

    @pytest.mark.asyncio
    async def test_maps_every_row_pair(self, vehicle_id: uuid.UUID) -> None:
        """Test that list_confirmed_by_price maps every (sale, replica) row pair to domain entities."""
        # Arrange
        sale_model = _make_sale_model(vehicle_id, status="CONFIRMED")
        replica_model = _make_replica_model(vehicle_id)
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = [(sale_model, replica_model)]
        session.execute.return_value = result
        repository = SQLAlchemySaleRepository(session)

        # Act
        pairs = await repository.list_confirmed_by_price()

        # Assert
        assert len(pairs) == 1
        sale, replica = pairs[0]
        assert sale.vehicle_id == vehicle_id
        assert replica.vehicle_id == vehicle_id
