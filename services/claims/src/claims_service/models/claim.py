import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Numeric, Sequence, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claims_service.db.base import Base

#: Human-facing claim reference, e.g. ``CLM-2026-000042``.
#:
#: Adjusters and policyholders quote this over the phone; the UUID primary key is
#: an internal identifier that services use to coordinate without a shared
#: sequence. Both exist deliberately: the UUID keeps writes uncoordinated across
#: services, while the reference gives operators something short and speakable.
#: The value is assigned by PostgreSQL from a sequence so concurrent inserts
#: cannot collide, and a unique index enforces that guarantee.
CLAIM_REFERENCE_SEQUENCE = "claim_reference_seq"
CLAIM_REFERENCE_PREFIX = "CLM"
CLAIM_REFERENCE_DIGITS = 6

#: Bound to the shared metadata so ``create_all`` emits ``CREATE SEQUENCE``
#: before the table that depends on it. Without this the column default would
#: reference a sequence that only the Alembic migration creates, so any schema
#: built from the models alone -- integration tests, local scratch databases --
#: would fail on first insert.
claim_reference_seq = Sequence(CLAIM_REFERENCE_SEQUENCE, metadata=Base.metadata)

CLAIM_REFERENCE_DEFAULT = text(
    f"'{CLAIM_REFERENCE_PREFIX}-' || to_char(now(), 'YYYY') || '-' || "
    f"lpad(nextval('{CLAIM_REFERENCE_SEQUENCE}')::text, {CLAIM_REFERENCE_DIGITS}, '0')"
)


def format_claim_reference(year: int, sequence_value: int) -> str:
    """Formats a claim reference the same way the database default does.

    Kept in Python so the format has a single tested definition that callers and
    fixtures can rely on without a database round trip.
    """
    return (
        f"{CLAIM_REFERENCE_PREFIX}-{year:04d}-"
        f"{sequence_value:0{CLAIM_REFERENCE_DIGITS}d}"
    )


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
    claim_reference: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        unique=True,
        index=True,
        server_default=CLAIM_REFERENCE_DEFAULT,
    )
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