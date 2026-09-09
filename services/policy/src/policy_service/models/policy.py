import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Enum, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from policy_service.db.base import Base


class PolicyStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_UNDERWRITING = "pending_underwriting"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RENEWED = "renewed"


class Policy(Base):
    __tablename__ = "policy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policyholder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    coverage_type: Mapped[str] = mapped_column(String(100), nullable=False)
    coverage_limits: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, name="policy_status"), nullable=False, default=PolicyStatus.DRAFT
    )
    premium_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    audit_records: Mapped[list["AuditRecord"]] = relationship(back_populates="policy")