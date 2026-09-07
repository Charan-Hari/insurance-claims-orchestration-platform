"""Create policy and audit record tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_policy_and_audit_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    policy_status = postgresql.ENUM(
        "DRAFT",
        "PENDING_UNDERWRITING",
        "ACTIVE",
        "CANCELLED",
        "EXPIRED",
        "RENEWED",
        name="policy_status",
    )
    op.create_table(
        "policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policyholder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("coverage_type", sa.String(length=100), nullable=False),
        sa.Column("coverage_limits", postgresql.JSONB(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("status", policy_status, nullable=False),
        sa.Column("premium_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_policyholder_id", "policy", ["policyholder_id"])
    op.create_table(
        "audit_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("old_status", policy_status, nullable=False),
        sa.Column("new_status", policy_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policy.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_record_policy_id", "audit_record", ["policy_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_record_policy_id", table_name="audit_record")
    op.drop_table("audit_record")
    op.drop_index("ix_policy_policyholder_id", table_name="policy")
    op.drop_table("policy")
    sa.Enum(name="policy_status").drop(op.get_bind(), checkfirst=True)