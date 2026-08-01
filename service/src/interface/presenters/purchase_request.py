import uuid
from datetime import date

from pydantic import BaseModel, Field


class PurchaseRequest(BaseModel):
    """Corpo da requisição de compra de um veículo."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo a ser comprado")
    buyer_cpf: str = Field(..., pattern=r"^\d{11}$", description="CPF do comprador, somente dígitos")
    sale_date: date = Field(..., description="Data da venda")
