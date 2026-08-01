from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Sale, SaleStatus, VehicleReplica
from src.domain.repositories import SaleRepository
from src.infrastructure.models import SaleModel, VehicleReplicaModel
from src.interface.gateways.vehicle_replica_gateway import map_replica_model_to_entity


class SQLAlchemySaleRepository(SaleRepository):
    """Adapter que implementa SaleRepository usando SQLAlchemy sobre PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, sale: Sale) -> Sale:
        """
        Persiste uma nova venda na transação corrente.

        Args:
            sale: Venda a ser criada.

        Returns:
            A venda persistida.
        """
        model = SaleModel(
            id=sale.id,
            vehicle_id=sale.vehicle_id,
            buyer_cpf=sale.buyer_cpf,
            sale_price=sale.sale_price,
            payment_code=sale.payment_code,
            status=sale.status.value,
            sale_date=sale.sale_date,
            confirmed_at=sale.confirmed_at,
            canceled_at=sale.canceled_at,
            created_at=sale.created_at,
            updated_at=sale.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._model_to_entity(model)

    async def get_by_payment_code(self, payment_code: str) -> Sale | None:
        """
        Busca uma venda pelo código de pagamento.

        Args:
            payment_code: Código opaco entregue à entidade de pagamento.

        Returns:
            Venda encontrada ou None.
        """
        stmt = select(SaleModel).where(SaleModel.payment_code == payment_code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._model_to_entity(model)

    async def transition_status(self, payment_code: str, from_status: SaleStatus, to_status: SaleStatus) -> Sale | None:
        """
        Aplica um UPDATE condicional de status com RETURNING, guardado pelo status atual.

        Args:
            payment_code: Código de pagamento da venda.
            from_status: Status exigido para que a transição ocorra.
            to_status: Status resultante.

        Returns:
            A venda atualizada, ou None se o status atual não era `from_status`.
        """
        moment = datetime.now(UTC)
        values: dict[str, Any] = {"status": to_status.value, "updated_at": moment}
        if to_status is SaleStatus.CONFIRMED:
            values["confirmed_at"] = moment
        elif to_status is SaleStatus.CANCELED:
            values["canceled_at"] = moment

        stmt = (
            update(SaleModel)
            .where(SaleModel.payment_code == payment_code, SaleModel.status == from_status.value)
            .values(**values)
            .returning(SaleModel)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        model = result.scalars().one_or_none()
        if model is None:
            return None
        return self._model_to_entity(model)

    async def list_confirmed_by_price(self) -> list[tuple[Sale, VehicleReplica]]:
        """
        Lista as vendas confirmadas com os dados do veículo, ordenadas por preço de venda crescente.

        Returns:
            Lista de pares (venda, réplica do veículo) ordenada por `sale_price`.
        """
        stmt = (
            select(SaleModel, VehicleReplicaModel)
            .join(VehicleReplicaModel, SaleModel.vehicle_id == VehicleReplicaModel.vehicle_id)
            .where(SaleModel.status == SaleStatus.CONFIRMED.value)
            .order_by(SaleModel.sale_price.asc())
        )
        result = await self._session.execute(stmt)
        return [
            (self._model_to_entity(sale_model), map_replica_model_to_entity(replica_model))
            for sale_model, replica_model in result.all()
        ]

    @staticmethod
    def _model_to_entity(model: SaleModel) -> Sale:
        """
        Converte SaleModel (ORM) para a entidade de domínio Sale.

        Args:
            model: Registro ORM da venda.

        Returns:
            Entidade de domínio equivalente.
        """
        return Sale(
            id=model.id,
            vehicle_id=model.vehicle_id,
            buyer_cpf=model.buyer_cpf,
            sale_price=model.sale_price,
            payment_code=model.payment_code,
            status=SaleStatus(model.status),
            sale_date=model.sale_date,
            confirmed_at=model.confirmed_at,
            canceled_at=model.canceled_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
