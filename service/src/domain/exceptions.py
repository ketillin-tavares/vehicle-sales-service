class DomainError(Exception):
    """Exceção base para erros de domínio do vehicle-sales-service."""


class VehicleNotFoundError(DomainError):
    """Lançada quando o veículo informado não existe na réplica local do catálogo."""


class VehicleUnavailableError(DomainError):
    """Lançada quando o veículo não está no status exigido pela transição solicitada."""


class SaleNotFoundError(DomainError):
    """Lançada quando não existe venda para o código de pagamento informado."""


class InvalidPaymentTransitionError(DomainError):
    """Lançada quando a transição de status da venda é ilegal (ex.: cancelar uma venda já confirmada)."""


class InvalidCpfError(DomainError):
    """Lançada quando o CPF do comprador é inválido (formato ou dígitos verificadores)."""
