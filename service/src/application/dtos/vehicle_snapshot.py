import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class VehicleSnapshot(BaseModel):
    """DTO de entrada com o snapshot de catálogo publicado pelo vehicle-core-service."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo no Core")
    brand: str = Field(..., min_length=1, max_length=100, description="Marca do veículo")
    model: str = Field(..., min_length=1, max_length=100, description="Modelo do veículo")
    year: int = Field(..., ge=1900, le=2100, description="Ano de fabricação do veículo")
    color: str = Field(..., min_length=1, max_length=50, description="Cor do veículo")
    price: Decimal = Field(..., gt=0, description="Preço de catálogo do veículo")
    version: int = Field(..., ge=1, description="Versão do catálogo no Core, usada como guarda de ordenação")
