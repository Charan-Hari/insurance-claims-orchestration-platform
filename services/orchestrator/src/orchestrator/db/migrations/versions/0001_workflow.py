"""Create orchestrator workflow tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_workflow"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    workflow_state = postgresql.ENUM(
        "PENDING",
        "POLICY_VERIFIED",
        "CLAIM_SUBMITTED",
        "COMPLETED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
        name="workflow_state",
        create_type=False,
    )
    workflow_step_state = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        name="workflow_step_state",
        create_type=False,
    )

    workflow_state.create(op.get_bind(), checkfirst=True)
    workflow_step_state.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workflow",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policyholder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", workflow_state, nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_policy_id", "workflow", ["policy_id"])
    op.create_index("ix_workflow_policyholder_id", "workflow", ["policyholder_id"])

    op.create_table(
        "workflow_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("state", workflow_step_state, nullable=False),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_id", "name", name="uq_workflow_step_name"),
    )
    op.create_index("ix_workflow_step_workflow_id", "workflow_step", ["workflow_id"])

    op.create_table(
        "workflow_idempotency_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("subject", "idempotency_key", name="uq_workflow_idempotency_subject_key"),
        sa.UniqueConstraint("workflow_id", name="uq_workflow_idempotency_workflow_id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_idempotency_key")
    op.drop_index("ix_workflow_step_workflow_id", table_name="workflow_step")
    op.drop_table("workflow_step")
    op.drop_index("ix_workflow_policyholder_id", table_name="workflow")
    op.drop_index("ix_workflow_policy_id", table_name="workflow")
    op.drop_table("workflow")
    op.execute("DROP TYPE IF EXISTS workflow_step_state")
    op.execute("DROP TYPE IF EXISTS workflow_state")
