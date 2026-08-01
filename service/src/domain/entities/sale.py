import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from src.domain.exceptions import InvalidCpfError, InvalidPaymentTransitionError

CPF_LENGTH = 11


def _is_valid_cpf(cpf: str) -> bool:
    """
    Verifica se um CPF é válido segundo seus dígitos verificadores.

    Args:
        cpf: CPF contendo exatamente 11 dígitos numéricos.

    Returns:
        True se o CPF for estruturalmente válido, False caso contrário.
    """
    if len(cpf) != CPF_LENGTH or not cpf.isdigit():
        return False
    if cpf == cpf[0] * CPF_LENGTH:
        return False

    digits = [int(digit) for digit in cpf]
    first_sum = sum(digits[index] * (10 - index) for index in range(9))
    first_check = (first_sum * 10 % 11) % 10
    second_sum = sum(digits[index] * (11 - index) for index in range(10))
    second_check = (second_sum * 10 % 11) % 10

    return first_check == digits[9] and second_check == digits[10]


class SaleStatus(StrEnum):
    """Status possíveis do ciclo de vida de uma venda."""

    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


class Sale(BaseModel):
    """Entidade que representa a venda de um veículo e seu ciclo de pagamento."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único da venda")
    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo comprado")
    buyer_cpf: str = Field(..., description="CPF do comprador, somente dígitos")
    sale_price: Decimal = Field(..., gt=0, description="Preço congelado no momento da compra")
    payment_code: str = Field(..., min_length=1, max_length=64, description="Código opaco de correlação do pagamento")
    status: SaleStatus = Field(default=SaleStatus.PENDING_PAYMENT, description="Status atual da venda")
    sale_date: date = Field(..., description="Data da venda informada na compra")
    confirmed_at: datetime | None = Field(default=None, description="Momento da confirmação do pagamento")
    canceled_at: datetime | None = Field(default=None, description="Momento do cancelamento do pagamento")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento de criação da venda",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento da última alteração da venda",
    )

    @field_validator("buyer_cpf")
    @classmethod
    def validate_buyer_cpf(cls, value: str) -> str:
        """
        Valida o CPF do comprador (formato e dígitos verificadores).

        Args:
            value: CPF informado na compra.

        Returns:
            O CPF normalizado com apenas dígitos.

        Raises:
            InvalidCpfError: Se o CPF não for válido.
        """
        if not _is_valid_cpf(value):
            raise InvalidCpfError(f"CPF inválido: {value}")
        return value

    def confirm_payment(self) -> None:
        """
        Confirma o pagamento da venda.

        Raises:
            InvalidPaymentTransitionError: Se a venda não estiver aguardando pagamento.
        """
        if self.status is not SaleStatus.PENDING_PAYMENT:
            raise InvalidPaymentTransitionError(
                f"Venda {self.payment_code} está em {self.status} e não pode ser confirmada"
            )
        moment = datetime.now(UTC)
        self.status = SaleStatus.CONFIRMED
        self.confirmed_at = moment
        self.updated_at = moment

    def cancel(self) -> None:
        """
        Cancela a venda por não pagamento.

        Raises:
            InvalidPaymentTransitionError: Se a venda não estiver aguardando pagamento.
        """
        if self.status is not SaleStatus.PENDING_PAYMENT:
            raise InvalidPaymentTransitionError(
                f"Venda {self.payment_code} está em {self.status} e não pode ser cancelada"
            )
        moment = datetime.now(UTC)
        self.status = SaleStatus.CANCELED
        self.canceled_at = moment
        self.updated_at = moment
