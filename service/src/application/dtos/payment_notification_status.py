from enum import StrEnum


class PaymentNotificationStatus(StrEnum):
    """Status enviados pela entidade de pagamento no webhook."""

    PAID = "paid"
    CANCELED = "canceled"
