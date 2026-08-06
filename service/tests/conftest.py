import os
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

# DATABASE_PASSWORD, INTERNAL_API_TOKEN e PAYMENT_WEBHOOK_TOKEN são obrigatórios em
# src.environment.Settings; precisam estar definidos antes de qualquer import de src.main,
# que resolve as settings em tempo de import.
os.environ.setdefault("DATABASE_PASSWORD", "vehicle_sales_pass")
os.environ.setdefault("INTERNAL_API_TOKEN", "internal-token")
os.environ.setdefault("PAYMENT_WEBHOOK_TOKEN", "webhook-token")

from src.application.ports import CoreNotifier  # noqa: E402
from src.domain.entities import Sale, VehicleReplica  # noqa: E402
from src.domain.repositories import SaleRepository, VehicleReplicaRepository  # noqa: E402
from src.main import app  # noqa: E402

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
