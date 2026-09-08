"""Add idempotent claim creation support."""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_claim_idempotency"
down_revision = "0001_claim_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim_idempotency_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", name="uq_claim_idempotency_claim_id"),
        sa.UniqueConstraint(
            "subject",
            "idempotency_key",
            name="uq_claim_idempotency_subject_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("claim_idempotency_key")
