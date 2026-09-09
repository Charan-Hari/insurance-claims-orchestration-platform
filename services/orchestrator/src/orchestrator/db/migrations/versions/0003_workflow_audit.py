"""Add workflow audit events."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_workflow_audit"
down_revision = "0002_workflow_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_audit_event_workflow_id",
        "workflow_audit_event",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_audit_event_workflow_id",
        table_name="workflow_audit_event",
    )
    op.drop_table("workflow_audit_event")
