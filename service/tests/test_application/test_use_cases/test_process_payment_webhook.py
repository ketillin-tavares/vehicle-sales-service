import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.application.dtos import PaymentNotificationStatus
from src.application.use_cases.process_payment_webhook import ProcessPaymentWebhook
from src.domain.entities import Sale, SaleStatus, VehicleStatus
from src.domain.exceptions import InvalidPaymentTransitionError, SaleNotFoundError
from src.domain.repositories import SaleRepository, VehicleReplicaRepository

VALID_CPF = "52998224725"
PAYMENT_CODE = "payment-code-123"


def _make_sale(vehicle_id: uuid.UUID, status: SaleStatus) -> Sale:
    """
    Constrói uma venda de exemplo com o status informado, usada para simular o retorno do repositório.

    Args:
        vehicle_id: Identificador do veículo associado à venda.
        status: Status atual da venda.

    Returns:
        Instância de Sale pronta para uso nos testes.
    """
    return Sale(
        vehicle_id=vehicle_id,
        buyer_cpf=VALID_CPF,
        sale_price=Decimal("95000.00"),
        payment_code=PAYMENT_CODE,
        status=status,
        sale_date=date(2026, 1, 15),
    )


class TestProcessPaymentWebhookPaid:
    """Tests for the 'paid' branch of ProcessPaymentWebhook.execute()."""

    @pytest.mark.asyncio
    async def test_paid_notification_confirms_sale_and_marks_vehicle_sold(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a first 'paid' notification transitions the sale to CONFIRMED and the vehicle to SOLD."""
        # Arrange
        confirmed_sale = _make_sale(vehicle_id, SaleStatus.CONFIRMED)
        mock_sale_repository.transition_status = AsyncMock(return_value=confirmed_sale)
        mock_vehicle_replica_repository.set_status = AsyncMock()
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act
        result = await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.PAID)

        # Assert
        assert result.status is SaleStatus.CONFIRMED
        assert result.vehicle_id == vehicle_id
        mock_sale_repository.transition_status.assert_awaited_once_with(
            PAYMENT_CODE, SaleStatus.PENDING_PAYMENT, SaleStatus.CONFIRMED
        )
        mock_vehicle_replica_repository.set_status.assert_awaited_once_with(vehicle_id, VehicleStatus.SOLD)

    @pytest.mark.asyncio
    async def test_repeated_paid_notification_is_idempotent(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a repeated 'paid' notification for an already CONFIRMED sale is a no-op success."""
        # Arrange
        already_confirmed = _make_sale(vehicle_id, SaleStatus.CONFIRMED)
        mock_sale_repository.transition_status = AsyncMock(return_value=None)
        mock_sale_repository.get_by_payment_code = AsyncMock(return_value=already_confirmed)
        mock_vehicle_replica_repository.set_status = AsyncMock()
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act
        result = await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.PAID)

        # Assert
        assert result.status is SaleStatus.CONFIRMED
        mock_vehicle_replica_repository.set_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_paid_notification_after_canceled_sale_raises_conflict(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a 'paid' notification for a CANCELED sale raises InvalidPaymentTransitionError."""
        # Arrange
        canceled_sale = _make_sale(vehicle_id, SaleStatus.CANCELED)
        mock_sale_repository.transition_status = AsyncMock(return_value=None)
        mock_sale_repository.get_by_payment_code = AsyncMock(return_value=canceled_sale)
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.PAID)


class TestProcessPaymentWebhookCanceled:
    """Tests for the 'canceled' branch of ProcessPaymentWebhook.execute()."""

    @pytest.mark.asyncio
    async def test_canceled_notification_cancels_sale_and_releases_vehicle(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a first 'canceled' notification transitions the sale to CANCELED and vehicle to AVAILABLE."""
        # Arrange
        canceled_sale = _make_sale(vehicle_id, SaleStatus.CANCELED)
        mock_sale_repository.transition_status = AsyncMock(return_value=canceled_sale)
        mock_vehicle_replica_repository.set_status = AsyncMock()
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act
        result = await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.CANCELED)

        # Assert
        assert result.status is SaleStatus.CANCELED
        mock_sale_repository.transition_status.assert_awaited_once_with(
            PAYMENT_CODE, SaleStatus.PENDING_PAYMENT, SaleStatus.CANCELED
        )
        mock_vehicle_replica_repository.set_status.assert_awaited_once_with(vehicle_id, VehicleStatus.AVAILABLE)

    @pytest.mark.asyncio
    async def test_repeated_canceled_notification_is_idempotent(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a repeated 'canceled' notification for an already CANCELED sale is a no-op success."""
        # Arrange
        already_canceled = _make_sale(vehicle_id, SaleStatus.CANCELED)
        mock_sale_repository.transition_status = AsyncMock(return_value=None)
        mock_sale_repository.get_by_payment_code = AsyncMock(return_value=already_canceled)
        mock_vehicle_replica_repository.set_status = AsyncMock()
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act
        result = await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.CANCELED)

        # Assert
        assert result.status is SaleStatus.CANCELED
        mock_vehicle_replica_repository.set_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_canceled_notification_after_confirmed_sale_raises_conflict(
        self,
        vehicle_id: uuid.UUID,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a 'canceled' notification for a CONFIRMED sale raises InvalidPaymentTransitionError."""
        # Arrange
        confirmed_sale = _make_sale(vehicle_id, SaleStatus.CONFIRMED)
        mock_sale_repository.transition_status = AsyncMock(return_value=None)
        mock_sale_repository.get_by_payment_code = AsyncMock(return_value=confirmed_sale)
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            await use_case.execute(PAYMENT_CODE, PaymentNotificationStatus.CANCELED)


class TestProcessPaymentWebhookUnknownCode:
    """Tests for notifications targeting an unknown payment_code."""

    @pytest.mark.asyncio
    async def test_unknown_payment_code_raises_sale_not_found(
        self,
        mock_sale_repository: SaleRepository,
        mock_vehicle_replica_repository: VehicleReplicaRepository,
    ) -> None:
        """Test that a notification for a non-existent payment_code raises SaleNotFoundError."""
        # Arrange
        mock_sale_repository.transition_status = AsyncMock(return_value=None)
        mock_sale_repository.get_by_payment_code = AsyncMock(return_value=None)
        use_case = ProcessPaymentWebhook(
            sale_repository=mock_sale_repository,
            vehicle_replica_repository=mock_vehicle_replica_repository,
        )

        # Act / Assert
        with pytest.raises(SaleNotFoundError):
            await use_case.execute("unknown-code", PaymentNotificationStatus.PAID)
