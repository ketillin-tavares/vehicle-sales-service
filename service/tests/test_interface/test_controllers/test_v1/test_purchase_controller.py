import uuid
from collections.abc import AsyncGenerator, Iterator
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import PurchaseResponse
from src.application.ports import CoreNotifier
from src.domain.entities import SaleStatus
from src.domain.exceptions import VehicleNotFoundError, VehicleUnavailableError
from src.infrastructure.database import get_session
from src.interface.controllers.dependencies import get_core_notifier
from src.interface.controllers.v1 import purchase_controller
from src.main import app

VALID_CPF = "52998224725"


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


class TestPurchaseVehicleRoute:
    """Tests for POST /v1/purchases."""

    @pytest.mark.asyncio
    async def test_purchase_happy_path_returns_201(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_core_notifier: CoreNotifier
    ) -> None:
        """Test that a successful purchase returns 201 with the sale data and notifies the Core in the background."""
        # Arrange
        vehicle_id = uuid.uuid4()
        expected = PurchaseResponse(
            sale_id=uuid.uuid4(),
            vehicle_id=vehicle_id,
            sale_price=Decimal("95000.00"),
            payment_code="abc123",
            status=SaleStatus.PENDING_PAYMENT,
        )
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = expected
        monkeypatch.setattr(purchase_controller, "PurchaseVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.post(
            "/v1/purchases",
            json={"vehicle_id": str(vehicle_id), "buyer_cpf": VALID_CPF, "sale_date": "2026-01-20"},
        )

        # Assert
        assert response.status_code == 201
        payload = response.json()
        assert payload["vehicle_id"] == str(vehicle_id)
        assert payload["payment_code"] == "abc123"
        assert payload["status"] == "PENDING_PAYMENT"
        mock_core_notifier.notify_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_purchase_unknown_vehicle_returns_404(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that purchasing an unknown vehicle returns 404."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleNotFoundError(f"Veículo {vehicle_id} não encontrado")
        monkeypatch.setattr(purchase_controller, "PurchaseVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.post(
            "/v1/purchases",
            json={"vehicle_id": str(vehicle_id), "buyer_cpf": VALID_CPF, "sale_date": "2026-01-20"},
        )

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_purchase_unavailable_vehicle_returns_409(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that purchasing an unavailable vehicle returns 409."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = VehicleUnavailableError(f"Veículo {vehicle_id} não está disponível")
        monkeypatch.setattr(purchase_controller, "PurchaseVehicle", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.post(
            "/v1/purchases",
            json={"vehicle_id": str(vehicle_id), "buyer_cpf": VALID_CPF, "sale_date": "2026-01-20"},
        )

        # Assert
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_purchase_with_malformed_cpf_returns_422(self, async_client: AsyncClient) -> None:
        """Test that a buyer_cpf failing the request schema pattern returns 422 without reaching the use case."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.post(
            "/v1/purchases",
            json={"vehicle_id": str(vehicle_id), "buyer_cpf": "123", "sale_date": "2026-01-20"},
        )

        # Assert
        assert response.status_code == 422
