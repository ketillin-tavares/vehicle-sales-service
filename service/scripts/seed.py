"""Popula o banco do vehicle-sales-service com as réplicas e vendas de demonstração.

O script é idempotente: registros cujo identificador já existe são ignorados.
Os identificadores das réplicas são fixos e correlacionados 1:1 com o seed do vehicle-core-service.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from pydantic import BaseModel, Field
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import SaleStatus, VehicleStatus
from src.environment import get_settings
from src.infrastructure.database import async_engine, async_session_factory
from src.infrastructure.models import SaleModel, VehicleReplicaModel
from src.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger()

SEED_VERSION = 1

RESERVED_VEHICLE_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
SOLD_VEHICLE_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")


class SeedVehicleReplica(BaseModel):
    """Réplica de veículo fixa do conjunto de dados de demonstração."""

    vehicle_id: uuid.UUID = Field(..., description="Identificador fixo do veículo, cunhado pelo vehicle-core-service")
    brand: str = Field(..., description="Marca do veículo")
    model: str = Field(..., description="Modelo do veículo")
    year: int = Field(..., description="Ano de fabricação do veículo")
    color: str = Field(..., description="Cor do veículo")
    price: Decimal = Field(..., description="Preço de catálogo do veículo")
    status: VehicleStatus = Field(..., description="Status comercial do veículo no conjunto de demonstração")


class SeedSale(BaseModel):
    """Venda fixa do conjunto de dados de demonstração."""

    id: uuid.UUID = Field(..., description="Identificador fixo da venda")
    vehicle_id: uuid.UUID = Field(..., description="Identificador do veículo vendido")
    buyer_cpf: str = Field(..., description="CPF válido do comprador, somente dígitos")
    sale_price: Decimal = Field(..., description="Preço congelado no momento da compra")
    payment_code: str = Field(..., description="Código fixo de correlação do pagamento")
    status: SaleStatus = Field(..., description="Status da venda no conjunto de demonstração")
    sale_date: date = Field(..., description="Data da venda")
    confirmed_at: datetime | None = Field(default=None, description="Momento da confirmação do pagamento, se houver")


SEED_VEHICLE_REPLICAS: list[SeedVehicleReplica] = [
    SeedVehicleReplica(
        vehicle_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        brand="Volkswagen",
        model="Gol",
        year=2018,
        color="Branco",
        price=Decimal("30000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicleReplica(
        vehicle_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        brand="Fiat",
        model="Uno",
        year=2020,
        color="Vermelho",
        price=Decimal("45000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicleReplica(
        vehicle_id=RESERVED_VEHICLE_ID,
        brand="Hyundai",
        model="HB20",
        year=2021,
        color="Prata",
        price=Decimal("58000.00"),
        status=VehicleStatus.RESERVED,
    ),
    SeedVehicleReplica(
        vehicle_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        brand="Chevrolet",
        model="Onix",
        year=2022,
        color="Preto",
        price=Decimal("62000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
    SeedVehicleReplica(
        vehicle_id=SOLD_VEHICLE_ID,
        brand="Honda",
        model="Civic",
        year=2019,
        color="Cinza",
        price=Decimal("98000.00"),
        status=VehicleStatus.SOLD,
    ),
    SeedVehicleReplica(
        vehicle_id=uuid.UUID("66666666-6666-4666-8666-666666666666"),
        brand="Toyota",
        model="Corolla",
        year=2023,
        color="Azul",
        price=Decimal("135000.00"),
        status=VehicleStatus.AVAILABLE,
    ),
]

SEED_SALES: list[SeedSale] = [
    SeedSale(
        id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001"),
        vehicle_id=RESERVED_VEHICLE_ID,
        buyer_cpf="52998224725",
        sale_price=Decimal("58000.00"),
        payment_code="SEED-PAY-PENDING-0001",
        status=SaleStatus.PENDING_PAYMENT,
        sale_date=date(2026, 7, 20),
        confirmed_at=None,
    ),
    SeedSale(
        id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002"),
        vehicle_id=SOLD_VEHICLE_ID,
        buyer_cpf="11144477735",
        sale_price=Decimal("98000.00"),
        payment_code="SEED-PAY-CONFIRMED-0002",
        status=SaleStatus.CONFIRMED,
        sale_date=date(2026, 7, 10),
        confirmed_at=datetime(2026, 7, 10, 14, 30, tzinfo=UTC),
    ),
]


async def insert_vehicle_replica(session: AsyncSession, replica: SeedVehicleReplica, moment: datetime) -> bool:
    """
    Insere uma réplica de veículo do conjunto fixo, ignorando o registro caso ele já exista.

    Args:
        session: Sessão async do SQLAlchemy usada na transação do seed.
        replica: Réplica fixa a ser inserida.
        moment: Carimbo de tempo aplicado a synced_at, created_at e updated_at.

    Returns:
        True se a réplica foi inserida; False se já existia e foi ignorada.
    """
    stmt = insert(VehicleReplicaModel).values(
        vehicle_id=replica.vehicle_id,
        brand=replica.brand,
        model=replica.model,
        year=replica.year,
        color=replica.color,
        price=replica.price,
        status=replica.status.value,
        version=SEED_VERSION,
        synced_at=moment,
        created_at=moment,
        updated_at=moment,
    )
    result = cast(CursorResult[Any], await session.execute(stmt.on_conflict_do_nothing()))
    return result.rowcount > 0


async def insert_sale(session: AsyncSession, sale: SeedSale, moment: datetime) -> bool:
    """
    Insere uma venda do conjunto fixo, ignorando o registro caso ele já exista.

    Args:
        session: Sessão async do SQLAlchemy usada na transação do seed.
        sale: Venda fixa a ser inserida.
        moment: Carimbo de tempo aplicado a created_at e updated_at.

    Returns:
        True se a venda foi inserida; False se já existia e foi ignorada.
    """
    stmt = insert(SaleModel).values(
        id=sale.id,
        vehicle_id=sale.vehicle_id,
        buyer_cpf=sale.buyer_cpf,
        sale_price=sale.sale_price,
        payment_code=sale.payment_code,
        status=sale.status.value,
        sale_date=sale.sale_date,
        confirmed_at=sale.confirmed_at,
        canceled_at=None,
        created_at=moment,
        updated_at=moment,
    )
    result = cast(CursorResult[Any], await session.execute(stmt.on_conflict_do_nothing()))
    return result.rowcount > 0


async def seed_vehicle_replicas(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """
    Aplica o seed das réplicas de veículo, registrando cada linha inserida ou ignorada.

    Args:
        session: Sessão async do SQLAlchemy usada na transação do seed.
        moment: Carimbo de tempo aplicado aos registros inseridos.

    Returns:
        Par (inseridos, ignorados) referente às réplicas de veículo.
    """
    inserted = 0
    skipped = 0
    for replica in SEED_VEHICLE_REPLICAS:
        if await insert_vehicle_replica(session, replica, moment):
            inserted += 1
            logger.info(
                "seed_replica_inserida",
                vehicle_id=str(replica.vehicle_id),
                model=replica.model,
                status=replica.status.value,
            )
        else:
            skipped += 1
            logger.info("seed_replica_ignorada", vehicle_id=str(replica.vehicle_id), model=replica.model)
    return inserted, skipped


async def seed_sales(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """
    Aplica o seed das vendas, registrando cada linha inserida ou ignorada.

    Args:
        session: Sessão async do SQLAlchemy usada na transação do seed.
        moment: Carimbo de tempo aplicado aos registros inseridos.

    Returns:
        Par (inseridos, ignorados) referente às vendas.
    """
    inserted = 0
    skipped = 0
    for sale in SEED_SALES:
        if await insert_sale(session, sale, moment):
            inserted += 1
            logger.info(
                "seed_venda_inserida",
                sale_id=str(sale.id),
                payment_code=sale.payment_code,
                status=sale.status.value,
            )
        else:
            skipped += 1
            logger.info("seed_venda_ignorada", sale_id=str(sale.id), payment_code=sale.payment_code)
    return inserted, skipped


async def main() -> None:
    """Executa o seed das réplicas e das vendas e registra o resultado consolidado."""
    settings = get_settings()
    configure_logging(settings.app.log_level)
    moment = datetime.now(UTC)

    async with async_session_factory() as session:
        replicas_inserted, replicas_skipped = await seed_vehicle_replicas(session, moment)
        sales_inserted, sales_skipped = await seed_sales(session, moment)
        await session.commit()

    await async_engine.dispose()
    logger.info(
        "seed_concluido",
        replicas_inserted=replicas_inserted,
        replicas_skipped=replicas_skipped,
        sales_inserted=sales_inserted,
        sales_skipped=sales_skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
