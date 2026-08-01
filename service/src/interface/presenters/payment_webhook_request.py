from pydantic import BaseModel, Field

from src.application.dtos import PaymentNotificationStatus


class PaymentWebhookRequest(BaseModel):
    """Corpo da notificação enviada pela entidade de pagamento."""

    payment_code: str = Field(..., min_length=1, max_length=64, description="Código de pagamento da venda")
    status: PaymentNotificationStatus = Field(..., description="Status do pagamento notificado (paid ou canceled)")
