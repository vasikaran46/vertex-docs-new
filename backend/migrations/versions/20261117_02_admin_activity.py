"""Add admin role and privacy-conscious activity log storage."""

from alembic import op
import sqlalchemy as sa
from migrations.schema_checks import validate_empty_activity_log_table


revision = "20261117_02"
down_revision = "20261117_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    offline = op.get_context().as_sql
    inspector = sa.inspect(bind) if not offline else None
    has_activity_table = bool(inspector and inspector.has_table("activity_logs"))
    if has_activity_table:
        # Validate before the users table is altered; never drop, recreate, or
        # silently adopt a non-empty or structurally different table.
        validate_empty_activity_log_table(bind)
    if inspector and "is_admin" in {column["name"] for column in inspector.get_columns("users")}:
        raise RuntimeError("users.is_admin already exists; refusing partial or untracked migration state")

    admin_default = sa.text("0") if bind.dialect.name == "sqlite" else sa.false()
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=admin_default),
    )
    if not has_activity_table:
        op.create_table(
            "activity_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("entity_type", sa.String(length=80), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            if_not_exists=offline,
        )
        op.create_index(
            "ix_activity_logs_user_created_at", "activity_logs", ["user_id", "created_at"],
            if_not_exists=offline,
        )
        op.create_index(
            "ix_activity_logs_action_created_at", "activity_logs", ["action", "created_at"],
            if_not_exists=offline,
        )


def downgrade() -> None:
    # Restoring a pre-migration backup is safer than dropping recorded activity.
    raise RuntimeError("This admin foundation migration is forward-only; restore a verified backup to roll back.")
