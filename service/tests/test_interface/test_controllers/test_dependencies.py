from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from src.environment import get_settings
from src.interface.controllers import dependencies
from src.interface.gateways import HttpCoreNotifier


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


class TestVerifyWebhookToken:
    """Tests for the verify_webhook_token dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_passes(self) -> None:
        """Test that a matching X-Webhook-Token header does not raise."""
        # Arrange
        expected = get_settings().security.payment_webhook_token

        # Act / Assert
        await dependencies.verify_webhook_token(x_webhook_token=expected)

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self) -> None:
        """Test that a missing X-Webhook-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_webhook_token(x_webhook_token=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_raises_401(self) -> None:
        """Test that a divergent X-Webhook-Token header raises HTTPException 401."""
        # Arrange / Act / Assert
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_webhook_token(x_webhook_token="wrong-token")
        assert exc_info.value.status_code == 401


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
