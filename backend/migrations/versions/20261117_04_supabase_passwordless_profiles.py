"""Allow Supabase-managed accounts without a duplicate local password hash."""

from alembic import op
import sqlalchemy as sa


revision = "20261117_04"
down_revision = "20261117_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    raise RuntimeError("This authentication migration is forward-only; restore a verified backup to roll back.")
