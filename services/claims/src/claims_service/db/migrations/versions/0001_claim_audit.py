"""Create claim and audit record tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_claim_audit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    claim_status = postgresql.ENUM(
        "SUBMITTED", "UNDER_REVIEW", "APPROVED", "DENIED", "PAID", "CLOSED", name="claim_status"
    )
    op.create_table(
        "claim",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policyholder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("adjuster_notes", sa.Text(), nullable=True),
        sa.Column("status", claim_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_policy_id", "claim", ["policy_id"])
    op.create_index("ix_claim_policyholder_id", "claim", ["policyholder_id"])
    op.create_table(
        "audit_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("old_status", claim_status, nullable=False),
        sa.Column("new_status", claim_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_record_claim_id", "audit_record", ["claim_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_record_claim_id", table_name="audit_record")
    op.drop_table("audit_record")
    op.drop_index("ix_claim_policyholder_id", table_name="claim")
    op.drop_index("ix_claim_policy_id", table_name="claim")
    op.drop_table("claim")
    sa.Enum(name="claim_status").drop(op.get_bind(), checkfirst=True)