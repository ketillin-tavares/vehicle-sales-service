import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class VehicleListingResponse(BaseModel):
    """DTO de resposta para um veículo disponível na listagem de venda."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo")
    brand: str = Field(..., description="Marca do veículo")
    model: str = Field(..., description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., description="Cor do veículo")
    price: Decimal = Field(..., description="Preço de catálogo do veículo")
