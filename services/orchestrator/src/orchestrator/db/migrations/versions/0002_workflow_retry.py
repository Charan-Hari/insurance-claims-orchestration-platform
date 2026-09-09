"""Persist workflow request data for safe retries."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_workflow_retry"
down_revision = "0001_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow",
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow", "request_payload")
