import uuid
from collections.abc import AsyncGenerator, Iterator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import PaymentWebhookResponse
from src.application.ports import CoreNotifier
from src.domain.entities import SaleStatus
from src.domain.exceptions import InvalidPaymentTransitionError, SaleNotFoundError
from src.environment import get_settings
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_core_notifier
from src.interface.controllers.v1 import payment_webhook_controller
from src.main import app


async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão assíncrona falsa, evitando qualquer conexão real com o banco."""
    yield AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def _override_dependencies(mock_core_notifier: CoreNotifier) -> Iterator[CoreNotifier]:
    """Sobrescreve as dependências de sessão e notificador do Core durante os testes de rota."""
    app.dependency_overrides[get_session] = _fake_get_session
    app.dependency_overrides[get_core_notifier] = lambda: mock_core_notifier
    yield mock_core_notifier
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_core_notifier, None)


class TestPaymentWebhookRoute:
    """Tests for POST /webhooks/v1/payments."""

    @pytest.mark.asyncio
    async def test_paid_notification_returns_200(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_core_notifier: CoreNotifier
    ) -> None:
        """Test that a valid 'paid' notification with the correct token returns 200 and notifies the Core."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = PaymentWebhookResponse(payment_code="pay-1", vehicle_id=vehicle_id, status=SaleStatus.CONFIRMED)
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(payment_webhook_controller, "ProcessPaymentWebhook", lambda **kwargs: mock_use_case)
        token = get_settings().security.payment_webhook_token

        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "pay-1", "status": "paid"},
            headers={"X-Webhook-Token": token},
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"
        mock_core_notifier.notify_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a webhook request without the X-Webhook-Token header returns 401."""
        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "pay-1", "status": "paid"},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a webhook request with an invalid X-Webhook-Token header returns 401."""
        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "pay-1", "status": "paid"},
            headers={"X-Webhook-Token": "wrong-token"},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_non_ascii_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a non-ASCII X-Webhook-Token header returns a clean 401 instead of a 500."""
        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "pay-1", "status": "paid"},
            headers={"X-Webhook-Token": "ç".encode("latin-1")},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_payment_code_returns_404(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a notification for an unknown payment_code returns 404."""
        # Arrange
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = SaleNotFoundError("Venda não encontrada")
        monkeypatch.setattr(payment_webhook_controller, "ProcessPaymentWebhook", lambda **kwargs: mock_use_case)
        token = get_settings().security.payment_webhook_token

        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "unknown", "status": "paid"},
            headers={"X-Webhook-Token": token},
        )

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_conflicting_transition_returns_409(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a notification conflicting with the current sale status returns 409."""
        # Arrange
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = InvalidPaymentTransitionError("Transição inválida")
        monkeypatch.setattr(payment_webhook_controller, "ProcessPaymentWebhook", lambda **kwargs: mock_use_case)
        token = get_settings().security.payment_webhook_token

        # Act
        response = await async_client.post(
            "/webhooks/v1/payments",
            json={"payment_code": "pay-1", "status": "canceled"},
            headers={"X-Webhook-Token": token},
        )

        # Assert
        assert response.status_code == 409
