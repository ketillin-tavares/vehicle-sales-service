from datetime import UTC, datetime

from src.application.dtos import VehicleSnapshot
from src.domain.entities import VehicleReplica
from src.domain.repositories import VehicleReplicaRepository
from src.infrastructure.observability.logging import get_logger

logger = get_logger()


class UpsertVehicleReplica:
    """Caso de uso para aplicar um snapshot de catálogo publicado pelo vehicle-core-service."""

    def __init__(self, vehicle_replica_repository: VehicleReplicaRepository) -> None:
        self._vehicle_replica_repository = vehicle_replica_repository

    async def execute(self, snapshot: VehicleSnapshot) -> bool:
        """
        Aplica o snapshot recebido à réplica local, respeitando a guarda de versão.

        Args:
            snapshot: Snapshot de catálogo enviado pelo Core.

        Returns:
            True se o snapshot foi aplicado; False se foi descartado por ser obsoleto.
        """
        now = datetime.now(UTC)
        replica = VehicleReplica(
            vehicle_id=snapshot.vehicle_id,
            brand=snapshot.brand,
            model=snapshot.model,
            year=snapshot.year,
            color=snapshot.color,
            price=snapshot.price,
            version=snapshot.version,
            synced_at=now,
            created_at=now,
            updated_at=now,
        )
        applied = await self._vehicle_replica_repository.upsert_snapshot(replica)

        logger.info(
            "snapshot_catalogo_recebido",
            vehicle_id=str(snapshot.vehicle_id),
            version=snapshot.version,
            applied=applied,
        )
        return applied
