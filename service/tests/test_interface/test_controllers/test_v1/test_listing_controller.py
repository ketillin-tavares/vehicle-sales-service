import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import SoldVehicleResponse, VehicleListingResponse
from src.infrastructure.database import get_session
from src.interface.controllers.v1 import listing_controller
from src.main import app

VALID_CPF = "52998224725"


async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão assíncrona falsa, evitando qualquer conexão real com o banco."""
    yield AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def _override_session() -> Iterator[None]:
    """Sobrescreve a dependência get_session por uma sessão falsa durante os testes de rota."""
    app.dependency_overrides[get_session] = _fake_get_session
    yield
    app.dependency_overrides.pop(get_session, None)


class TestListVehiclesForSaleRoute:
    """Tests for GET /v1/vehicles/for-sale."""

    @pytest.mark.asyncio
    async def test_returns_200_with_ascending_price_order(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the route returns 200 with the listing ordered as produced by the use case."""
        # Arrange
        cheap = VehicleListingResponse(
            vehicle_id=uuid.uuid4(), brand="Fiat", model="Uno", year=2015, color="Branco", price=Decimal("30000.00")
        )
        expensive = VehicleListingResponse(
            vehicle_id=uuid.uuid4(), brand="BMW", model="X1", year=2023, color="Preto", price=Decimal("250000.00")
        )
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = [cheap, expensive]
        monkeypatch.setattr(listing_controller, "ListVehiclesForSale", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.get("/v1/vehicles/for-sale")

        # Assert
        assert response.status_code == 200
        payload = response.json()
        assert [item["price"] for item in payload] == ["30000.00", "250000.00"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_vehicles_available(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the route returns an empty list with 200 when no vehicles are available."""
        # Arrange
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = []
        monkeypatch.setattr(listing_controller, "ListVehiclesForSale", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.get("/v1/vehicles/for-sale")

        # Assert
        assert response.status_code == 200
        assert response.json() == []


class TestListSoldVehiclesRoute:
    """Tests for GET /v1/vehicles/sold."""

    @pytest.mark.asyncio
    async def test_returns_200_with_ascending_sale_price_order(
        self, async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the route returns 200 with sold vehicles ordered as produced by the use case."""
        # Arrange
        cheap = SoldVehicleResponse(
            sale_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            brand="Fiat",
            model="Palio",
            year=2016,
            color="Cinza",
            sale_price=Decimal("40000.00"),
            buyer_cpf=VALID_CPF,
            sale_date=date(2026, 1, 5),
        )
        expensive = SoldVehicleResponse(
            sale_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            brand="Audi",
            model="A4",
            year=2024,
            color="Branco",
            sale_price=Decimal("300000.00"),
            buyer_cpf=VALID_CPF,
            sale_date=date(2026, 1, 6),
        )
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = [cheap, expensive]
        monkeypatch.setattr(listing_controller, "ListSoldVehicles", lambda **kwargs: mock_use_case)

        # Act
        response = await async_client.get("/v1/vehicles/sold")

        # Assert
        assert response.status_code == 200
        payload = response.json()
        assert [item["sale_price"] for item in payload] == ["40000.00", "300000.00"]
