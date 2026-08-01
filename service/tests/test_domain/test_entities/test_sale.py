import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.domain.entities.sale import Sale, SaleStatus
from src.domain.exceptions import InvalidCpfError, InvalidPaymentTransitionError

VALID_CPF = "52998224725"


def _make_sale(status: SaleStatus = SaleStatus.PENDING_PAYMENT) -> Sale:
    """
    Constrói uma venda de exemplo com o status informado.

    Args:
        status: Status inicial da venda.

    Returns:
        Instância de Sale pronta para uso nos testes.
    """
    return Sale(
        vehicle_id=uuid.uuid4(),
        buyer_cpf=VALID_CPF,
        sale_price=Decimal("95000.00"),
        payment_code="payment-code",
        status=status,
        sale_date=date(2026, 1, 15),
    )


class TestSaleCpfValidation:
    """Tests for the CPF check-digit validation on Sale.buyer_cpf."""

    def test_valid_cpf_is_accepted(self) -> None:
        """Test that a structurally valid CPF is accepted without raising."""
        # Arrange / Act
        sale = _make_sale()

        # Assert
        assert sale.buyer_cpf == VALID_CPF

    def test_cpf_with_wrong_check_digits_raises(self) -> None:
        """Test that a CPF with incorrect check digits raises InvalidCpfError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidCpfError):
            Sale(
                vehicle_id=uuid.uuid4(),
                buyer_cpf="52998224726",
                sale_price=Decimal("95000.00"),
                payment_code="payment-code",
                sale_date=date(2026, 1, 15),
            )

    def test_cpf_with_all_same_digits_raises(self) -> None:
        """Test that a CPF composed of a single repeated digit raises InvalidCpfError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidCpfError):
            Sale(
                vehicle_id=uuid.uuid4(),
                buyer_cpf="11111111111",
                sale_price=Decimal("95000.00"),
                payment_code="payment-code",
                sale_date=date(2026, 1, 15),
            )

    def test_cpf_with_wrong_length_raises(self) -> None:
        """Test that a CPF with a length different from 11 raises InvalidCpfError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidCpfError):
            Sale(
                vehicle_id=uuid.uuid4(),
                buyer_cpf="5299822472",
                sale_price=Decimal("95000.00"),
                payment_code="payment-code",
                sale_date=date(2026, 1, 15),
            )

    def test_non_numeric_cpf_raises(self) -> None:
        """Test that a CPF containing non-numeric characters raises InvalidCpfError."""
        # Arrange / Act / Assert
        with pytest.raises(InvalidCpfError):
            Sale(
                vehicle_id=uuid.uuid4(),
                buyer_cpf="5299822472A",
                sale_price=Decimal("95000.00"),
                payment_code="payment-code",
                sale_date=date(2026, 1, 15),
            )


class TestSaleConfirmPayment:
    """Tests for the Sale.confirm_payment() state transition."""

    def test_confirm_payment_from_pending_transitions_to_confirmed(self) -> None:
        """Test that confirming a PENDING_PAYMENT sale moves it to CONFIRMED and sets confirmed_at."""
        # Arrange
        sale = _make_sale(status=SaleStatus.PENDING_PAYMENT)

        # Act
        sale.confirm_payment()

        # Assert
        assert sale.status is SaleStatus.CONFIRMED
        assert sale.confirmed_at is not None
        assert sale.canceled_at is None

    def test_confirm_payment_already_confirmed_raises(self) -> None:
        """Test that confirming an already CONFIRMED sale raises InvalidPaymentTransitionError."""
        # Arrange
        sale = _make_sale(status=SaleStatus.CONFIRMED)

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            sale.confirm_payment()

    def test_confirm_payment_canceled_sale_raises(self) -> None:
        """Test that confirming a CANCELED sale raises InvalidPaymentTransitionError."""
        # Arrange
        sale = _make_sale(status=SaleStatus.CANCELED)

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            sale.confirm_payment()


class TestSaleCancel:
    """Tests for the Sale.cancel() state transition."""

    def test_cancel_from_pending_transitions_to_canceled(self) -> None:
        """Test that canceling a PENDING_PAYMENT sale moves it to CANCELED and sets canceled_at."""
        # Arrange
        sale = _make_sale(status=SaleStatus.PENDING_PAYMENT)

        # Act
        sale.cancel()

        # Assert
        assert sale.status is SaleStatus.CANCELED
        assert sale.canceled_at is not None
        assert sale.confirmed_at is None

    def test_cancel_already_canceled_raises(self) -> None:
        """Test that canceling an already CANCELED sale raises InvalidPaymentTransitionError."""
        # Arrange
        sale = _make_sale(status=SaleStatus.CANCELED)

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            sale.cancel()

    def test_cancel_confirmed_sale_raises(self) -> None:
        """Test that canceling a CONFIRMED sale raises InvalidPaymentTransitionError."""
        # Arrange
        sale = _make_sale(status=SaleStatus.CONFIRMED)

        # Act / Assert
        with pytest.raises(InvalidPaymentTransitionError):
            sale.cancel()
