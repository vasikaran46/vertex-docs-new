"""Add an optional mapping from application users to Supabase Auth UUIDs."""

from alembic import op
import sqlalchemy as sa


revision = "20261117_03"
down_revision = "20261117_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("supabase_auth_id", sa.Uuid(as_uuid=False), nullable=True),
    )
    op.create_index(
        "ix_users_supabase_auth_id",
        "users",
        ["supabase_auth_id"],
        unique=True,
    )


def downgrade() -> None:
    # Once identities are linked, removing this column would sever the mapping.
    raise RuntimeError("This identity mapping migration is forward-only; do not remove linked account IDs.")
