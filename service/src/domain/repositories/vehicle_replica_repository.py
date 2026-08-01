import abc
import uuid

from src.domain.entities import VehicleReplica, VehicleStatus


class VehicleReplicaRepository(abc.ABC):
    """Port (interface) para persistência da réplica local do catálogo de veículos."""

    @abc.abstractmethod
    async def upsert_snapshot(self, replica: VehicleReplica) -> bool:
        """
        Aplica um snapshot de catálogo vindo do Core, protegido por versão.

        A implementação deve gravar apenas os campos de catálogo e a versão, nunca a coluna
        `status`, e deve ignorar snapshots cuja versão não seja maior que a já armazenada.

        Args:
            replica: Réplica montada a partir do snapshot recebido.

        Returns:
            True se o snapshot foi aplicado; False se foi descartado por ser obsoleto.
        """

    @abc.abstractmethod
    async def get_by_id(self, vehicle_id: uuid.UUID) -> VehicleReplica | None:
        """
        Busca uma réplica de veículo pelo seu identificador.

        Args:
            vehicle_id: Identificador do veículo.

        Returns:
            Réplica encontrada ou None.
        """

    @abc.abstractmethod
    async def list_available_by_price(self) -> list[VehicleReplica]:
        """
        Lista os veículos disponíveis para venda, ordenados por preço crescente.

        Returns:
            Lista de réplicas com status AVAILABLE ordenada por preço.
        """

    @abc.abstractmethod
    async def reserve(self, vehicle_id: uuid.UUID) -> bool:
        """
        Reserva atomicamente um veículo disponível.

        A implementação deve resolver a concorrência em uma única escrita condicional
        (AVAILABLE -> RESERVED), sem locks mantidos entre requisições.

        Args:
            vehicle_id: Identificador do veículo a reservar.

        Returns:
            True se a reserva foi obtida; False se o veículo não estava disponível.
        """

    @abc.abstractmethod
    async def set_status(self, vehicle_id: uuid.UUID, status: VehicleStatus) -> None:
        """
        Define o status comercial de um veículo.

        Args:
            vehicle_id: Identificador do veículo.
            status: Novo status comercial.
        """
