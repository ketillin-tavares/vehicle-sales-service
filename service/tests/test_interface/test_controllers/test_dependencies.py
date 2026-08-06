from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException, Request

from src.environment import get_settings
from src.interface.controllers import dependencies
from src.interface.gateways import HttpCoreNotifier


def _make_request(client_host: str | None) -> Request:
    """
    Constrói um Request falso expondo apenas o atributo `.client` usado por verify_webhook_token.

    Args:
        client_host: IP a ser exposto em `request.client.host`, ou None para simular ausência de client.

    Returns:
        Mock de Request com o atributo `client` configurado conforme solicitado.
    """
    request = MagicMock(spec=Request)
    request.client = MagicMock(host=client_host) if client_host is not None else None
    return request


class TestVerifyInternalToken:
    """Tests for the verify_internal_token dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_passes(self) -> None:
        """Test that a matching X-Internal-Token header does not raise."""
        # Arrange
        expected = get_settings().security.internal_api_token

        # Act / Assert
        await dependencies.verify_internal_token(x_internal_token=expected)

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self) -> None:
        """Test that a missing X-Internal-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_internal_token(x_internal_token=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_raises_401(self) -> None:
        """Test that a divergent X-Internal-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_internal_token(x_internal_token="wrong-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_ascii_token_raises_401_not_500(self) -> None:
        """Test that a non-ASCII X-Internal-Token header raises a clean 401 instead of an unhandled TypeError."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_internal_token(x_internal_token="ç")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_does_not_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a failed internal token check stays silent, without emitting any warning log."""
        # Arrange
        mock_logger = MagicMock()
        monkeypatch.setattr(dependencies, "logger", mock_logger)

        # Act
        with pytest.raises(HTTPException):
            await dependencies.verify_internal_token(x_internal_token="wrong-token")

        # Assert
        mock_logger.warning.assert_not_called()


class TestVerifyWebhookToken:
    """Tests for the verify_webhook_token dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_passes(self) -> None:
        """Test that a matching X-Webhook-Token header does not raise."""
        # Arrange
        expected = get_settings().security.payment_webhook_token
        request = _make_request(client_host="203.0.113.7")

        # Act / Assert
        await dependencies.verify_webhook_token(request=request, x_webhook_token=expected)

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self) -> None:
        """Test that a missing X-Webhook-Token header raises HTTPException 401."""
        # Arrange
        request = _make_request(client_host="203.0.113.7")

        # Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_webhook_token(request=request, x_webhook_token=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_raises_401(self) -> None:
        """Test that a divergent X-Webhook-Token header raises HTTPException 401."""
        # Arrange
        request = _make_request(client_host="203.0.113.7")

        # Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_webhook_token(request=request, x_webhook_token="wrong-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_ascii_token_raises_401_not_500(self) -> None:
        """Test that a non-ASCII X-Webhook-Token header raises a clean 401 instead of an unhandled TypeError."""
        # Arrange
        request = _make_request(client_host="203.0.113.7")

        # Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_webhook_token(request=request, x_webhook_token="ç")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_logs_single_warning_with_client_ip_but_not_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a failed webhook check logs exactly one warning with the client IP and never the token."""
        # Arrange
        mock_logger = MagicMock()
        monkeypatch.setattr(dependencies, "logger", mock_logger)
        request = _make_request(client_host="203.0.113.7")
        wrong_token = "wrong-token"  # noqa: S105

        # Act
        with pytest.raises(HTTPException):
            await dependencies.verify_webhook_token(request=request, x_webhook_token=wrong_token)

        # Assert
        mock_logger.warning.assert_called_once_with("webhook_pagamento_autenticacao_falhou", client_ip="203.0.113.7")
        assert wrong_token not in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_missing_client_falls_back_to_unknown_client_ip_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that verify_webhook_token uses the unknown-client placeholder when request.client is None."""
        # Arrange
        mock_logger = MagicMock()
        monkeypatch.setattr(dependencies, "logger", mock_logger)
        request = _make_request(client_host=None)

        # Act
        with pytest.raises(HTTPException):
            await dependencies.verify_webhook_token(request=request, x_webhook_token=None)

        # Assert
        mock_logger.warning.assert_called_once_with(
            "webhook_pagamento_autenticacao_falhou", client_ip=dependencies.UNKNOWN_CLIENT_IP
        )


class TestGetCoreNotifier:
    """Tests for the get_core_notifier dependency provider."""

    def test_returns_http_core_notifier_wired_with_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_core_notifier returns an HttpCoreNotifier wired from the shared HTTP client and settings."""
        # Arrange
        fake_client = MagicMock(spec=httpx.AsyncClient)
        monkeypatch.setattr(dependencies, "get_http_client", lambda: fake_client)
        settings = get_settings()

        # Act
        notifier = dependencies.get_core_notifier()

        # Assert
        assert isinstance(notifier, HttpCoreNotifier)
        assert notifier._client is fake_client  # noqa: SLF001
        assert notifier._base_url == settings.core_service.base_url.rstrip("/")  # noqa: SLF001
        assert notifier._internal_token == settings.security.internal_api_token  # noqa: SLF001
