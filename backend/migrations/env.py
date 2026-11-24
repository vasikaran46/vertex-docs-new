from alembic import context
from sqlalchemy import create_engine, inspect, pool

from migration_config import local_sqlite_migration_url, migration_database_url
from migrations.schema_checks import validate_empty_activity_log_table


config = context.config
BASE_REVISION = "20261117_01"
APP_TABLES = {"users", "documents", "assistant_conversations", "assistant_messages"}
LEGACY_COLUMNS = {
    "users": {"id", "name", "email", "password_hash", "theme", "language", "avatar"},
    "documents": {"id", "owner_id", "original_name", "stored_name", "content_type", "size"},
    "assistant_conversations": {"id", "owner_id", "title", "created_at", "updated_at"},
    "assistant_messages": {"id", "conversation_id", "role", "content", "created_at"},
}


def migration_url() -> tuple[str, bool]:
    targets = context.get_x_argument(as_dictionary=True)
    if targets.get("target") == "local-sqlite":
        return local_sqlite_migration_url(), True
    if "target" in targets:
        raise RuntimeError("Unsupported migration target")
    return migration_database_url(), False


def is_approved_legacy_stamp() -> bool:
    options = getattr(config, "cmd_opts", None)
    command_spec = getattr(options, "cmd", None)
    # Alembic's CLI stores `cmd` as (function, positional names, keyword names),
    # not as the function itself. Validate that tuple and the complete parsed
    # argument set so this exception cannot authorize another command/target.
    if not isinstance(command_spec, tuple) or len(command_spec) != 3:
        return False
    command, positional, keyword = command_spec
    return (
        getattr(command, "__module__", "") == "alembic.command"
        and getattr(command, "__name__", "") == "stamp"
        and tuple(positional) == ("revisions",)
        and set(keyword) == {"sql", "tag", "purge"}
        and getattr(options, "revisions", None) == [BASE_REVISION]
        and getattr(options, "x", None) == ["target=local-sqlite"]
        and getattr(options, "config", None) is None
        and getattr(options, "name", None) == "alembic"
        and not getattr(options, "sql", False)
        and getattr(options, "tag", None) is None
        and not getattr(options, "purge", False)
        and not getattr(options, "raiseerr", False)
        and not getattr(options, "quiet", False)
        and not getattr(options, "verbose", False)
    )


def verify_legacy_sqlite_schema(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if tables not in (APP_TABLES, APP_TABLES | {"activity_logs"}):
        raise RuntimeError("Local SQLite schema does not exactly match the verified legacy baseline")
    for table, expected_columns in LEGACY_COLUMNS.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table)}
        if actual_columns != expected_columns:
            raise RuntimeError("Local SQLite columns do not match the verified legacy baseline")
    if "activity_logs" in tables:
        validate_empty_activity_log_table(connection)


def run_migrations_offline() -> None:
    url, _ = migration_url()
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url, local_sqlite = migration_url()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        existing = set(inspect(connection).get_table_names())
        if existing.intersection(APP_TABLES) and "alembic_version" not in existing:
            if not local_sqlite or not is_approved_legacy_stamp():
                raise RuntimeError("Target contains application tables without migration history; refusing migration")
            verify_legacy_sqlite_schema(connection)
        # Inspection above starts SQLAlchemy's autobegin transaction. End that
        # read-only preflight transaction so Alembic does not mistake it for an
        # externally managed transaction and skip committing its own work.
        if connection.in_transaction():
            connection.rollback()
        context.configure(connection=connection, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
