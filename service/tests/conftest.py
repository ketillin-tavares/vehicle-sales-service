import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.application.ports import CoreNotifier
from src.domain.entities import Sale, VehicleReplica
from src.domain.repositories import SaleRepository, VehicleReplicaRepository
from src.main import app

VALID_CPF = "52998224725"
OTHER_VALID_CPF = "11144477735"


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """Fixture para cliente HTTP assíncrono contra a aplicação FastAPI em memória."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def vehicle_id() -> uuid.UUID:
    """Fixture com um UUID de veículo de exemplo."""
    return uuid.uuid4()


@pytest.fixture
def mock_vehicle_replica_repository() -> VehicleReplicaRepository:
    """Fixture com mock da interface VehicleReplicaRepository."""
    return AsyncMock(spec=VehicleReplicaRepository)


@pytest.fixture
def mock_sale_repository() -> SaleRepository:
    """Fixture com mock da interface SaleRepository."""
    return AsyncMock(spec=SaleRepository)


@pytest.fixture
def mock_core_notifier() -> CoreNotifier:
    """Fixture com mock da interface CoreNotifier."""
    return AsyncMock(spec=CoreNotifier)


@pytest.fixture
def sample_vehicle_replica(vehicle_id: uuid.UUID) -> VehicleReplica:
    """Fixture com uma réplica de veículo de exemplo, disponível para venda."""
    return VehicleReplica(
        vehicle_id=vehicle_id,
        brand="Toyota",
        model="Corolla",
        year=2022,
        color="Prata",
        price=Decimal("95000.00"),
        version=1,
    )


@pytest.fixture
def sample_sale(vehicle_id: uuid.UUID) -> Sale:
    """Fixture com uma venda de exemplo, aguardando pagamento."""
    return Sale(
        vehicle_id=vehicle_id,
        buyer_cpf=VALID_CPF,
        sale_price=Decimal("95000.00"),
        payment_code="sample-payment-code",
        sale_date=date(2026, 1, 15),
    )
