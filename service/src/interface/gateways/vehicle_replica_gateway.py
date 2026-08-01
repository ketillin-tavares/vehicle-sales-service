import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import VehicleReplica, VehicleStatus
from src.domain.repositories import VehicleReplicaRepository
from src.infrastructure.models import VehicleReplicaModel


def map_replica_model_to_entity(model: VehicleReplicaModel) -> VehicleReplica:
    """
    Converte VehicleReplicaModel (ORM) para a entidade de domínio VehicleReplica.

    Args:
        model: Registro ORM da réplica do veículo.

    Returns:
        Entidade de domínio equivalente.
    """
    return VehicleReplica(
        vehicle_id=model.vehicle_id,
        brand=model.brand,
        model=model.model,
        year=model.year,
        color=model.color,
        price=model.price,
        status=VehicleStatus(model.status),
        version=model.version,
        synced_at=model.synced_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyVehicleReplicaRepository(VehicleReplicaRepository):
    """Adapter que implementa VehicleReplicaRepository usando SQLAlchemy sobre PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_snapshot(self, replica: VehicleReplica) -> bool:
        """
        Aplica o snapshot de catálogo via INSERT ... ON CONFLICT DO UPDATE com guarda de versão.

        A coluna `status` é gravada apenas na inserção inicial (default AVAILABLE) e nunca é
        atualizada, preservando o estado comercial de propriedade do serviço de vendas.

        Args:
            replica: Réplica montada a partir do snapshot recebido.

        Returns:
            True se o snapshot foi aplicado; False se foi descartado por ser obsoleto.
        """
        stmt = insert(VehicleReplicaModel).values(
            vehicle_id=replica.vehicle_id,
            brand=replica.brand,
            model=replica.model,
            year=replica.year,
            color=replica.color,
            price=replica.price,
            status=replica.status.value,
            version=replica.version,
            synced_at=replica.synced_at,
            created_at=replica.created_at,
            updated_at=replica.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VehicleReplicaModel.vehicle_id],
            set_={
                "brand": stmt.excluded.brand,
                "model": stmt.excluded.model,
                "year": stmt.excluded.year,
                "color": stmt.excluded.color,
                "price": stmt.excluded.price,
                "version": stmt.excluded.version,
                "synced_at": stmt.excluded.synced_at,
                "updated_at": stmt.excluded.updated_at,
            },
            where=VehicleReplicaModel.version < stmt.excluded.version,
        )
        result = cast(CursorResult[Any], await self._session.execute(stmt))
        return result.rowcount > 0

    async def get_by_id(self, vehicle_id: uuid.UUID) -> VehicleReplica | None:
        """
        Busca uma réplica de veículo pelo seu identificador.

        Args:
            vehicle_id: Identificador do veículo.

        Returns:
            Réplica encontrada ou None.
        """
        stmt = select(VehicleReplicaModel).where(VehicleReplicaModel.vehicle_id == vehicle_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return map_replica_model_to_entity(model)

    async def list_available_by_price(self) -> list[VehicleReplica]:
        """
        Lista os veículos disponíveis para venda, ordenados por preço crescente.

        Returns:
            Lista de réplicas com status AVAILABLE ordenada por preço.
        """
        stmt = (
            select(VehicleReplicaModel)
            .where(VehicleReplicaModel.status == VehicleStatus.AVAILABLE.value)
            .order_by(VehicleReplicaModel.price.asc())
        )
        result = await self._session.execute(stmt)
        return [map_replica_model_to_entity(model) for model in result.scalars().all()]

    async def reserve(self, vehicle_id: uuid.UUID) -> bool:
        """
        Reserva o veículo com um único UPDATE condicional (AVAILABLE -> RESERVED).

        Args:
            vehicle_id: Identificador do veículo a reservar.

        Returns:
            True se a reserva foi obtida; False se o veículo não estava disponível.
        """
        stmt = (
            update(VehicleReplicaModel)
            .where(
                VehicleReplicaModel.vehicle_id == vehicle_id,
                VehicleReplicaModel.status == VehicleStatus.AVAILABLE.value,
            )
            .values(status=VehicleStatus.RESERVED.value, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        result = cast(CursorResult[Any], await self._session.execute(stmt))
        return result.rowcount > 0

    async def set_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Define o status comercial de um veículo.

        Args:
            vehicle_id: Identificador do veículo.
            status: Novo status comercial.
        """
        stmt = (
            update(VehicleReplicaModel)
            .where(VehicleReplicaModel.vehicle_id == vehicle_id)
            .values(status=status.value, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(stmt)
