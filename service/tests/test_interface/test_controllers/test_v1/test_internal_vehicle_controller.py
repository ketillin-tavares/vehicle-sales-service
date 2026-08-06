import uuid
from collections.abc import AsyncGenerator, Iterator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.environment import get_settings
from src.infrastructure.database import get_session
from src.interface.controllers.v1 import internal_vehicle_controller
from src.main import app


async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão assíncrona falsa, evitando qualquer conexão real com o banco."""
    yield AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def _override_session() -> Iterator[None]:
    """Sobrescreve a dependência get_session por uma sessão falsa durante os testes de rota."""
    app.dependency_overrides[get_session] = _fake_get_session
    yield
    app.dependency_overrides.pop(get_session, None)


class TestUpsertVehicleReplicaRoute:
    """Tests for PUT /internal/v1/vehicles/{vehicle_id}."""

    @pytest.mark.asyncio
    async def test_applied_snapshot_returns_200(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a valid internal snapshot with the correct token returns 200 with applied=True."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = True
        monkeypatch.setattr(internal_vehicle_controller, "UpsertVehicleReplica", lambda **kwargs: mock_use_case)
        token = get_settings().security.internal_api_token

        # Act
        response = await async_client.put(
            f"/internal/v1/vehicles/{vehicle_id}",
            json={"brand": "Fiat", "model": "Mobi", "year": 2022, "color": "Branco", "price": "60000.00", "version": 2},
            headers={"X-Internal-Token": token},
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"vehicle_id": str(vehicle_id), "applied": True}

    @pytest.mark.asyncio
    async def test_stale_snapshot_returns_200_with_applied_false(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a stale-version snapshot returns 200 with applied=False, without raising."""
        # Arrange
        vehicle_id = uuid.uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = False
        monkeypatch.setattr(internal_vehicle_controller, "UpsertVehicleReplica", lambda **kwargs: mock_use_case)
        token = get_settings().security.internal_api_token

        # Act
        response = await async_client.put(
            f"/internal/v1/vehicles/{vehicle_id}",
            json={"brand": "Fiat", "model": "Mobi", "year": 2022, "color": "Branco", "price": "60000.00", "version": 1},
            headers={"X-Internal-Token": token},
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"vehicle_id": str(vehicle_id), "applied": False}

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a snapshot request without X-Internal-Token returns 401."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.put(
            f"/internal/v1/vehicles/{vehicle_id}",
            json={"brand": "Fiat", "model": "Mobi", "year": 2022, "color": "Branco", "price": "60000.00", "version": 1},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a snapshot request with an invalid X-Internal-Token returns 401."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.put(
            f"/internal/v1/vehicles/{vehicle_id}",
            json={"brand": "Fiat", "model": "Mobi", "year": 2022, "color": "Branco", "price": "60000.00", "version": 1},
            headers={"X-Internal-Token": "wrong-token"},
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_non_ascii_token_returns_401(self, async_client: AsyncClient) -> None:
        """Test that a snapshot request with a non-ASCII X-Internal-Token returns a clean 401 instead of a 500."""
        # Arrange
        vehicle_id = uuid.uuid4()

        # Act
        response = await async_client.put(
            f"/internal/v1/vehicles/{vehicle_id}",
            json={"brand": "Fiat", "model": "Mobi", "year": 2022, "color": "Branco", "price": "60000.00", "version": 1},
            headers={"X-Internal-Token": "ç".encode("latin-1")},
        )

        # Assert
        assert response.status_code == 401
