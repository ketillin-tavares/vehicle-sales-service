import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.models.base import Base


class SaleModel(Base):
    """Modelo ORM para a tabela sales (ciclo de vida da venda e correlação de pagamento)."""

    __tablename__ = "sales"
    __table_args__ = (
        Index(
            "uq_sales_active_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING_PAYMENT', 'CONFIRMED')"),
        ),
        Index("idx_sales_status_sale_price", "status", "sale_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicle_replicas.vehicle_id"),
        nullable=False,
    )
    buyer_cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING_PAYMENT")
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
