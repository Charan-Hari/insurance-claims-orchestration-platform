import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from legacy_adapter.db.base import Base


class LegacyClaim(Base):
    __tablename__ = "legacy_claim"
    __table_args__ = (
        UniqueConstraint("source_system", "legacy_claim_id", name="uq_legacy_claim_source_record"),
        Index("ix_legacy_claim_received_at", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    legacy_claim_id: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String(255))
    policyholder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claim_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
