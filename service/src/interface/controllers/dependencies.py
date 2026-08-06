import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from src.application.ports import CoreNotifier
from src.environment import get_settings
from src.infrastructure.http import get_http_client
from src.infrastructure.observability.logging import get_logger
from src.interface.gateways import HttpCoreNotifier

logger = get_logger()

UNAUTHORIZED_DETAIL = "Token inválido ou ausente"
UNKNOWN_CLIENT_IP = "desconhecido"


def _tokens_match(received: str | None, expected: str) -> bool:
    """
    Compara o token recebido com o esperado em tempo constante.

    A comparação é feita sobre os bytes UTF-8 dos tokens, pois secrets.compare_digest
    lança TypeError para strings com caracteres fora do intervalo ASCII.

    Args:
        received: Token enviado no header da requisição.
        expected: Token configurado no serviço.

    Returns:
        True se o token estiver presente e for idêntico ao esperado, False caso contrário.
    """
    if received is None:
        return False
    return secrets.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))


def _assert_token(received: str | None, expected: str) -> None:
    """
    Valida o token recebido, rejeitando a requisição quando ele não confere.

    Args:
        received: Token enviado no header da requisição.
        expected: Token configurado no serviço.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    if not _tokens_match(received, expected):
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


async def verify_webhook_token(request: Request, x_webhook_token: Annotated[str | None, Header()] = None) -> None:
    """
    Valida o header X-Webhook-Token do webhook de pagamento.

    O webhook é exposto publicamente, então toda falha de autenticação é registrada
    com o IP de origem para permitir a detecção de tentativas de força bruta.
    O valor do token recebido nunca é registrado.

    Args:
        request: Requisição HTTP em curso, usada para obter o IP do cliente.
        x_webhook_token: Token compartilhado enviado pela entidade de pagamento.

    Raises:
        HTTPException: Com status 401 se o token estiver ausente ou for divergente.
    """
    if _tokens_match(x_webhook_token, get_settings().security.payment_webhook_token):
        return

    client_ip = request.client.host if request.client is not None else UNKNOWN_CLIENT_IP
    logger.warning("webhook_pagamento_autenticacao_falhou", client_ip=client_ip)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)


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
