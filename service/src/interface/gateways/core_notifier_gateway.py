import asyncio
import uuid

import httpx

from src.application.ports import CoreNotifier
from src.domain.entities import VehicleStatus
from src.infrastructure.observability.logging import get_logger

logger = get_logger()

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 0.5


class HttpCoreNotifier(CoreNotifier):
    """Adapter que notifica o vehicle-core-service via HTTP, com retentativa limitada e best-effort."""

    def __init__(self, client: httpx.AsyncClient, base_url: str, internal_token: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token

    async def notify_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Envia o novo status do veículo ao Core, absorvendo qualquer falha.

        Args:
            vehicle_id: Identificador do veículo.
            status: Status comercial a ser espelhado no Core.
        """
        url = f"{self._base_url}/internal/v1/vehicles/{vehicle_id}/status"
        headers = {"X-Internal-Token": self._internal_token}
        payload = {"status": status.value}

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await self._client.patch(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info("core_notificado", vehicle_id=str(vehicle_id), status=status.value, attempt=attempt)
                return
            except httpx.HTTPError as error:
                logger.warning(
                    "core_notificacao_falhou",
                    vehicle_id=str(vehicle_id),
                    status=status.value,
                    attempt=attempt,
                    erro=str(error),
                )
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(BACKOFF_SECONDS * attempt)

        logger.error("core_notificacao_desistida", vehicle_id=str(vehicle_id), status=status.value)
