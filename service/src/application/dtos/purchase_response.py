import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.entities import SaleStatus


class PurchaseResponse(BaseModel):
    """DTO de resposta da criação de uma compra."""

    sale_id: uuid.UUID = Field(..., description="Identificador da venda criada")
    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo reservado")
    sale_price: Decimal = Field(..., description="Preço congelado no momento da compra")
    payment_code: str = Field(..., description="Código a ser informado pela entidade de pagamento no webhook")
    status: SaleStatus = Field(..., description="Status da venda recém-criada")
