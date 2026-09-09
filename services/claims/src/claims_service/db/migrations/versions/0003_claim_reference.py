"""Add a human-facing claim reference.

Claims already have a UUID primary key, which lets services create records without
coordinating on a shared sequence. That identifier is not usable by people: an
adjuster cannot read it over the phone. This adds a short, speakable reference
(``CLM-2026-000042``) alongside it.

The value is produced by a PostgreSQL sequence in a column default rather than in
application code, so concurrent inserts cannot allocate the same number, and a
unique index enforces that guarantee independently of the application.

Existing rows are backfilled in creation order so their references match the order
the claims were actually filed.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_claim_reference"
down_revision = "0002_claim_idempotency"
branch_labels = None
depends_on = None

SEQUENCE_NAME = "claim_reference_seq"
REFERENCE_DEFAULT = (
    "'CLM-' || to_char(now(), 'YYYY') || '-' || "
    f"lpad(nextval('{SEQUENCE_NAME}')::text, 6, '0')"
)


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {SEQUENCE_NAME} START WITH 1"))

    # Added nullable so the backfill can run before the NOT NULL constraint applies.
    op.add_column("claim", sa.Column("claim_reference", sa.String(length=32), nullable=True))

    # Backfill in creation order, deriving the year from each claim's own
    # created_at so historical references stay truthful rather than all showing
    # the migration year.
    op.execute(
        sa.text(
            f"""
            WITH ordered AS (
                SELECT id,
                       created_at,
                       row_number() OVER (ORDER BY created_at, id) AS position
                FROM claim
            )
            UPDATE claim
            SET claim_reference = 'CLM-' || to_char(ordered.created_at, 'YYYY') || '-' ||
                                  lpad(ordered.position::text, 6, '0')
            FROM ordered
            WHERE claim.id = ordered.id
            """
        )
    )

    # Advance the sequence past the backfilled values so new claims never collide.
    op.execute(
        sa.text(
            f"SELECT setval('{SEQUENCE_NAME}', GREATEST((SELECT count(*) FROM claim), 1))"
        )
    )

    op.alter_column("claim", "claim_reference", nullable=False)
    op.alter_column("claim", "claim_reference", server_default=sa.text(REFERENCE_DEFAULT))
    op.create_index("ix_claim_claim_reference", "claim", ["claim_reference"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_claim_claim_reference", table_name="claim")
    op.drop_column("claim", "claim_reference")
    op.execute(sa.text(f"DROP SEQUENCE IF EXISTS {SEQUENCE_NAME}"))
