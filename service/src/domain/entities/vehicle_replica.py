import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from src.domain.exceptions import VehicleUnavailableError


class VehicleStatus(StrEnum):
    """Status comerciais possíveis de um veículo, de propriedade do serviço de vendas."""

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"


class VehicleReplica(BaseModel):
    """Réplica local (read model) do catálogo do Core, acrescida do status comercial."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo, cunhado pelo vehicle-core-service")
    brand: str = Field(..., min_length=1, max_length=100, description="Marca do veículo")
    model: str = Field(..., min_length=1, max_length=100, description="Modelo do veículo")
    year: int = Field(..., ge=1900, le=2100, description="Ano de fabricação do veículo")
    color: str = Field(..., min_length=1, max_length=50, description="Cor do veículo")
    price: Decimal = Field(..., gt=0, description="Preço de catálogo do veículo")
    status: VehicleStatus = Field(default=VehicleStatus.AVAILABLE, description="Status comercial atual do veículo")
    version: int = Field(..., ge=1, description="Última versão do catálogo aplicada a partir do Core")
    synced_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento da última sincronização recebida do Core",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento de criação da réplica",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Momento da última alteração da réplica",
    )

    def reserve(self) -> None:
        """
        Reserva o veículo para uma compra em andamento.

        Raises:
            VehicleUnavailableError: Se o veículo não estiver disponível.
        """
        if self.status is not VehicleStatus.AVAILABLE:
            raise VehicleUnavailableError(f"Veículo {self.vehicle_id} não está disponível para reserva")
        self._apply_status(VehicleStatus.RESERVED)

    def mark_sold(self) -> None:
        """
        Marca o veículo como vendido após a confirmação do pagamento.

        Raises:
            VehicleUnavailableError: Se o veículo não estiver reservado.
        """
        if self.status is not VehicleStatus.RESERVED:
            raise VehicleUnavailableError(f"Veículo {self.vehicle_id} não está reservado e não pode ser vendido")
        self._apply_status(VehicleStatus.SOLD)

    def release(self) -> None:
        """
        Devolve o veículo à listagem após o cancelamento do pagamento.

        Raises:
            VehicleUnavailableError: Se o veículo não estiver reservado.
        """
        if self.status is not VehicleStatus.RESERVED:
            raise VehicleUnavailableError(f"Veículo {self.vehicle_id} não está reservado e não pode ser liberado")
        self._apply_status(VehicleStatus.AVAILABLE)

    def _apply_status(self, status: VehicleStatus) -> None:
        """
        Aplica um novo status ao veículo e atualiza o carimbo de alteração.

        Args:
            status: Novo status comercial do veículo.
        """
        self.status = status
        self.updated_at = datetime.now(UTC)
