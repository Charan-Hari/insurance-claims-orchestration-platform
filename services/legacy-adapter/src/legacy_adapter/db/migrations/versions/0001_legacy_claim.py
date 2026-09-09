"""Create durable legacy claim records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_legacy_claim"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_claim",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("legacy_claim_id", sa.String(255), nullable=False),
        sa.Column("policy_number", sa.String(255)),
        sa.Column("policyholder_id", postgresql.UUID(as_uuid=True)),
        sa.Column("claim_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("incident_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_system", "legacy_claim_id", name="uq_legacy_claim_source_record"),
    )
    op.create_index("ix_legacy_claim_received_at", "legacy_claim", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_legacy_claim_received_at", table_name="legacy_claim")
    op.drop_table("legacy_claim")
