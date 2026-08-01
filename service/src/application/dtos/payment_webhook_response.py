import uuid

from pydantic import BaseModel, Field

from src.domain.entities import SaleStatus


class PaymentWebhookResponse(BaseModel):
    """DTO de resposta do processamento da notificação de pagamento."""

    payment_code: str = Field(..., description="Código de pagamento processado")
    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo associado à venda")
    status: SaleStatus = Field(..., description="Status da venda após o processamento")
