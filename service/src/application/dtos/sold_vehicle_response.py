import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class SoldVehicleResponse(BaseModel):
    """DTO de resposta para um veículo vendido, com os dados comerciais da venda."""

    sale_id: uuid.UUID = Field(..., description="Identificador da venda")
    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo vendido")
    brand: str = Field(..., description="Marca do veículo")
    model: str = Field(..., description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., description="Cor do veículo")
    sale_price: Decimal = Field(..., description="Preço congelado no momento da compra")
    buyer_cpf: str = Field(..., description="CPF do comprador, somente dígitos")
    sale_date: date = Field(..., description="Data da venda")
