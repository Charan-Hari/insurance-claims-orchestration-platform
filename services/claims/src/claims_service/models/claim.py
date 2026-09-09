import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claims_service.db.base import Base


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    PAID = "paid"
    CLOSED = "closed"


class Claim(Base):
    __tablename__ = "claim"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    policyholder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    claim_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    adjuster_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status"), nullable=False, default=ClaimStatus.SUBMITTED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    audit_records: Mapped[list["AuditRecord"]] = relationship(back_populates="claim")