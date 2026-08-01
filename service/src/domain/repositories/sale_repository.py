import abc

from src.domain.entities import Sale, SaleStatus, VehicleReplica


class SaleRepository(abc.ABC):
    """Port (interface) para persistência de vendas."""

    @abc.abstractmethod
    async def add(self, sale: Sale) -> Sale:
        """
        Persiste uma nova venda.

        Args:
            sale: Venda a ser criada.

        Returns:
            A venda persistida.
        """

    @abc.abstractmethod
    async def get_by_payment_code(self, payment_code: str) -> Sale | None:
        """
        Busca uma venda pelo código de pagamento.

        Args:
            payment_code: Código opaco entregue à entidade de pagamento.

        Returns:
            Venda encontrada ou None.
        """

    @abc.abstractmethod
    async def transition_status(self, payment_code: str, from_status: SaleStatus, to_status: SaleStatus) -> Sale | None:
        """
        Transiciona atomicamente o status de uma venda, condicionado ao status atual.

        A implementação deve aplicar a mudança em uma única escrita condicional, registrando
        o carimbo de confirmação ou cancelamento correspondente ao status de destino.

        Args:
            payment_code: Código de pagamento da venda.
            from_status: Status exigido para que a transição ocorra.
            to_status: Status resultante.

        Returns:
            A venda atualizada, ou None se o status atual não era `from_status`.
        """

    @abc.abstractmethod
    async def list_confirmed_by_price(self) -> list[tuple[Sale, VehicleReplica]]:
        """
        Lista as vendas confirmadas com os dados do veículo, ordenadas por preço de venda crescente.

        Returns:
            Lista de pares (venda, réplica do veículo) ordenada por `sale_price`.
        """
