import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from src.application.ports import CoreNotifier
from src.environment import get_settings
from src.infrastructure.http import get_http_client
from src.interface.gateways import HttpCoreNotifier

UNAUTHORIZED_DETAIL = "Token inválido ou ausente"


def _assert_token(received: str | None, expected: str) -> None:
    """
    Compara o token recebido com o esperado em tempo constante.

    Args:
        received: Token enviado no header da requisição.
        expected: Token configurado no serviço.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    if received is None or not secrets.compare_digest(received, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)


async def verify_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    """
    Valida o header X-Internal-Token das rotas internas entre serviços.

    Args:
        x_internal_token: Token compartilhado enviado pelo vehicle-core-service.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    _assert_token(x_internal_token, get_settings().security.internal_api_token)


async def verify_webhook_token(x_webhook_token: Annotated[str | None, Header()] = None) -> None:
    """
    Valida o header X-Webhook-Token do webhook de pagamento.

    Args:
        x_webhook_token: Token compartilhado enviado pela entidade de pagamento.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    _assert_token(x_webhook_token, get_settings().security.payment_webhook_token)


def get_core_notifier() -> CoreNotifier:
    """
    Fornece o notificador do vehicle-core-service usando o cliente HTTP compartilhado.

    Returns:
        Implementação HTTP da port CoreNotifier.
    """
    settings = get_settings()
    return HttpCoreNotifier(
        client=get_http_client(),
        base_url=settings.core_service.base_url,
        internal_token=settings.security.internal_api_token,
    )
