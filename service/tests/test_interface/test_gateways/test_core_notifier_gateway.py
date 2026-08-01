import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.domain.entities import VehicleStatus
from src.interface.gateways import core_notifier_gateway
from src.interface.gateways.core_notifier_gateway import HttpCoreNotifier


def _make_success_response() -> MagicMock:
    """
    Constrói uma resposta HTTP simulada de sucesso, cujo raise_for_status não levanta exceção.

    Returns:
        Mock de httpx.Response representando uma resposta 2xx.
    """
    response = MagicMock()
    response.raise_for_status = MagicMock()
    return response


class TestHttpCoreNotifierNotifyStatus:
    """Tests for HttpCoreNotifier.notify_status() retry and best-effort behavior."""

    @pytest.mark.asyncio
    async def test_notify_status_succeeds_on_first_attempt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a successful PATCH on the first attempt calls the Core exactly once."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.patch.return_value = _make_success_response()
        monkeypatch.setattr(core_notifier_gateway.asyncio, "sleep", AsyncMock())
        notifier = HttpCoreNotifier(client=mock_client, base_url="http://core:8000", internal_token="tok")

        # Act
        await notifier.notify_status(vehicle_id, VehicleStatus.SOLD)

        # Assert
        assert mock_client.patch.call_count == 1

    @pytest.mark.asyncio
    async def test_notify_status_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a transient failure followed by a success stops retrying and reports no error."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.patch.side_effect = [httpx.ConnectError("boom"), _make_success_response()]
        monkeypatch.setattr(core_notifier_gateway.asyncio, "sleep", AsyncMock())
        notifier = HttpCoreNotifier(client=mock_client, base_url="http://core:8000", internal_token="tok")

        # Act
        await notifier.notify_status(vehicle_id, VehicleStatus.SOLD)

        # Assert
        assert mock_client.patch.call_count == 2

    @pytest.mark.asyncio
    async def test_notify_status_swallows_failure_after_max_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that persistent failures are absorbed (never raised) after exhausting all retry attempts."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.patch.side_effect = httpx.ConnectError("boom")
        monkeypatch.setattr(core_notifier_gateway.asyncio, "sleep", AsyncMock())
        notifier = HttpCoreNotifier(client=mock_client, base_url="http://core:8000", internal_token="tok")

        # Act
        await notifier.notify_status(vehicle_id, VehicleStatus.SOLD)

        # Assert
        assert mock_client.patch.call_count == core_notifier_gateway.MAX_ATTEMPTS
