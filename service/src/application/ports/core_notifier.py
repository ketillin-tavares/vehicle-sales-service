import abc
import uuid

from src.domain.entities import VehicleStatus


class CoreNotifier(abc.ABC):
    """Port (interface) para notificar o vehicle-core-service sobre mudanças de status."""

    @abc.abstractmethod
    async def notify_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Informa ao Core o novo status comercial de um veículo.

        Contrato best-effort: a implementação nunca propaga erros para o chamador — falhas de
        rede ou do Core são registradas em log e absorvidas, pois a disponibilidade das vendas
        não pode depender do Core.

        Args:
            vehicle_id: Identificador do veículo.
            status: Status comercial a ser espelhado no Core.
        """
