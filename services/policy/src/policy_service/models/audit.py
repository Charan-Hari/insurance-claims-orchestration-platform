import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from policy_service.db.base import Base
from policy_service.models.policy import PolicyStatus


class AuditRecord(Base):
    __tablename__ = "audit_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    old_status: Mapped[PolicyStatus] = mapped_column(Enum(PolicyStatus, name="policy_status"), nullable=False)
    new_status: Mapped[PolicyStatus] = mapped_column(Enum(PolicyStatus, name="policy_status"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    policy: Mapped["Policy"] = relationship(back_populates="audit_records")