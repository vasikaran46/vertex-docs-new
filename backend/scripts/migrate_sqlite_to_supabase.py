"""Dry-run-first import of a verified SQLite snapshot into an empty PostgreSQL schema.

Document files are never copied, changed, or deleted. Their backup/local paths
are checked before import; only relational metadata is migrated.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, MetaData, Table, create_engine, inspect, text


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from migration_config import migration_database_url


DEFAULT_SOURCE_BACKUP = BACKEND_DIR.parent / "backups" / "pre-supabase-20261117-162252"
LOCAL_STORAGE = BACKEND_DIR / "storage"
TABLES = (
    "users",
    "documents",
    "assistant_conversations",
    "assistant_messages",
    "activity_logs",
)
EXPECTED_COLUMNS = {
    "users": {"id", "name", "email", "password_hash", "theme", "language", "avatar", "is_admin"},
    "documents": {"id", "owner_id", "original_name", "stored_name", "content_type", "size"},
    "assistant_conversations": {"id", "owner_id", "title", "created_at", "updated_at"},
    "assistant_messages": {"id", "conversation_id", "role", "content", "created_at"},
    "activity_logs": {"id", "user_id", "action", "entity_type", "entity_id", "metadata", "created_at"},
}
EXPECTED_REVISION = "20261117_02"
RELATIONSHIPS = {
    "documents": ("owner_id", "users", "id"),
    "assistant_conversations": ("owner_id", "users", "id"),
    "assistant_messages": ("conversation_id", "assistant_conversations", "id"),
    "activity_logs": ("user_id", "users", "id"),
}


class MigrationValidationError(RuntimeError):
    """Safe validation failures that may be shown to the caller."""


class MigrationPhaseError(RuntimeError):
    """Unexpected failure with safe phase metadata and no driver message."""

    def __init__(self, phase: str, exception_class: str):
        self.phase = phase
        self.exception_class = exception_class
        super().__init__(phase, exception_class)


POSTGRES_TYPES = {
    "users": {"id": Integer, "name": (String, 120), "email": (String, 255), "password_hash": (String, 255), "theme": (String, 24), "language": (String, 20), "avatar": (String, 80), "is_admin": Boolean},
    "documents": {"id": Integer, "owner_id": Integer, "original_name": (String, 255), "stored_name": (String, 255), "content_type": (String, 120), "size": Integer},
    "assistant_conversations": {"id": Integer, "owner_id": Integer, "title": (String, 120), "created_at": DateTime, "updated_at": DateTime},
    "assistant_messages": {"id": Integer, "conversation_id": Integer, "role": (String, 16), "content": Text, "created_at": DateTime},
    "activity_logs": {"id": Integer, "user_id": Integer, "action": (String, 80), "entity_type": (String, 80), "entity_id": Integer, "metadata": JSON, "created_at": DateTime},
}
NOT_NULL_COLUMNS = {
    "users": {"id", "name", "email", "password_hash", "theme", "language", "avatar", "is_admin"},
    "documents": {"id", "owner_id", "original_name", "stored_name", "content_type", "size"},
    "assistant_conversations": {"id", "owner_id", "title", "created_at", "updated_at"},
    "assistant_messages": {"id", "conversation_id", "role", "content", "created_at"},
    "activity_logs": {"id", "user_id", "action", "entity_type", "metadata", "created_at"},
}


def safe_error(exc: BaseException) -> None:
    # Only emit phase and exception type; never include exception messages.
    phase = getattr(exc, "phase", "unclassified")
    exception_class = getattr(exc, "exception_class", type(exc).__name__)
    print(f"Migration stopped during {phase} ({exception_class}).", file=sys.stderr)


def resolve_source(source_backup: Path) -> tuple[Path, Path]:
    source = source_backup.expanduser().resolve()
    if source.is_dir():
        return source / "vertex_docs.db", source / "storage"
    return source, source.parent / "storage"


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]


def read_source(source_backup: Path, local_storage: Path = LOCAL_STORAGE) -> dict[str, list[dict[str, object]]]:
    source_path, backup_storage = resolve_source(source_backup)
    if not source_path.is_file():
        raise MigrationValidationError("Configured SQLite source backup was not found")
    source = sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationValidationError("SQLite integrity check failed")
        if source.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise MigrationValidationError("SQLite foreign-key check failed")
        source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "alembic_version" in source_tables:
            source_revisions = [row[0] for row in source.execute("SELECT version_num FROM alembic_version")]
            if source_revisions != [EXPECTED_REVISION]:
                raise MigrationValidationError("Source backup Alembic revision is not 20261117_02")
        actual_tables = {
            row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if row[0] != "sqlite_sequence"
        }
        missing = set(TABLES) - actual_tables
        if missing:
            raise MigrationValidationError("Source backup is missing required application tables")
        for table, expected in EXPECTED_COLUMNS.items():
            actual = {row[1] for row in source.execute(f'PRAGMA table_info("{table}")')}
            if actual != expected:
                raise MigrationValidationError("Source backup table schema does not match the expected application schema")

        data = {table: _rows(source, table) for table in TABLES}
        for table, fields in {
            "assistant_conversations": ("created_at", "updated_at"),
            "assistant_messages": ("created_at",),
            "activity_logs": ("created_at",),
        }.items():
            for row in data[table]:
                for field in fields:
                    value = row[field]
                    if isinstance(value, str):
                        row[field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # SQLite stores SQLAlchemy JSON values as serialized text. Decode them
        # so the PostgreSQL JSON type can serialize them safely during insert.
        for activity in data["activity_logs"]:
            value = activity["metadata"]
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (TypeError, ValueError) as exc:
                    raise MigrationValidationError("Source activity metadata is not valid JSON") from exc
            if not isinstance(value, dict):
                raise MigrationValidationError("Source activity metadata must be a JSON object")
            activity["metadata"] = value

        for document in data["documents"]:
            name = document["stored_name"]
            if not isinstance(name, str) or not name or Path(name).name != name:
                raise MigrationValidationError("Unsafe stored document path found in source backup")
            if not (backup_storage / name).is_file() and not (local_storage / name).is_file():
                raise MigrationValidationError("A referenced local document file is missing")
        return data
    finally:
        source.close()


def _target_preflight(connection) -> None:
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    missing = (set(TABLES) | {"alembic_version"}) - existing
    if missing:
        raise MigrationValidationError("Target schema or Alembic version table is incomplete")
    for table, expected in EXPECTED_COLUMNS.items():
        if {column["name"] for column in inspector.get_columns(table)} != expected:
            raise MigrationValidationError("Target table schema does not match the expected application schema")
    for table, (column, referred_table, referred_column) in RELATIONSHIPS.items():
        foreign_keys = inspector.get_foreign_keys(table)
        required = next((fk for fk in foreign_keys if fk["constrained_columns"] == [column]
                         and fk["referred_table"] == referred_table
                         and fk["referred_columns"] == [referred_column]), None)
        if required is None:
            raise MigrationValidationError("Target schema is missing a required foreign-key constraint")
        if (connection.dialect.name == "postgresql" and table == "assistant_messages"
                and (required.get("options", {}).get("ondelete") or "").upper() != "CASCADE"):
            raise MigrationValidationError("Target message foreign-key delete behavior is incompatible")
    if connection.dialect.name == "postgresql":
        _validate_postgres_schema(connection, inspector)
    versions = [row[0] for row in connection.execute(text("SELECT version_num FROM alembic_version")).all()]
    if versions != [EXPECTED_REVISION]:
        raise MigrationValidationError("Target Alembic revision must be exactly 20261117_02")
    counts = {
        table: connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
        for table in TABLES
    }
    if any(counts.values()):
        raise MigrationValidationError("Target application tables are not empty; refusing duplicate import")


def _is_sequence_default(value: object) -> bool:
    # PostgreSQL serial defaults use nextval('sequence_name'::regclass).
    # Do not use normalized(), which removes the parentheses from this syntax.
    expression = "".join(str(value or "").lower().split())
    return expression.startswith("nextval('") and expression.endswith("'::regclass)")


def _validate_postgres_schema(connection, inspector) -> None:
    for table, columns in POSTGRES_TYPES.items():
        inspected = {column["name"]: column for column in inspector.get_columns(table)}
        primary_key = inspector.get_pk_constraint(table).get("constrained_columns") or []
        if primary_key != ["id"]:
            raise MigrationValidationError("Target primary-key schema is incompatible")
        for name, expected in columns.items():
            column = inspected[name]
            expected_type, *length = expected if isinstance(expected, tuple) else (expected,)
            if not isinstance(column["type"], expected_type):
                raise MigrationValidationError("Target PostgreSQL column type is incompatible")
            if length and getattr(column["type"], "length", None) != length[0]:
                raise MigrationValidationError("Target PostgreSQL column length is incompatible")
            if column["nullable"] != (name not in NOT_NULL_COLUMNS[table]):
                raise MigrationValidationError("Target PostgreSQL column nullability is incompatible")

    # Check named ID defaults through PostgreSQL's catalog so serial and identity
    # columns are both supported. Other server defaults are part of migrations 02.
    for table in TABLES:
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"), {"table_name": table}
        ).scalar_one_or_none()
        if not sequence:
            raise MigrationValidationError("Target primary-key generation default is missing")
    defaults = {table: {c["name"]: c.get("default") for c in inspector.get_columns(table)} for table in TABLES}
    inspected_columns = {table: {c["name"]: c for c in inspector.get_columns(table)} for table in TABLES}
    def normalized(value):
        return "".join(str(value or "").lower().split()).replace("(", "").replace(")", "")
    for table in TABLES:
        identity = inspected_columns[table]["id"].get("identity")
        sequence_default = _is_sequence_default(defaults[table]["id"])
        if not identity and not sequence_default:
            raise MigrationValidationError("Target primary-key generation default is missing")
    if normalized(defaults["users"]["is_admin"]) not in {"false", "false::boolean"}:
        raise MigrationValidationError("Target admin default is incompatible")
    if normalized(defaults["activity_logs"]["metadata"]) not in {"'{}'::json", "'{}'::jsonb"}:
        raise MigrationValidationError("Target activity metadata default is incompatible")
    if normalized(defaults["activity_logs"]["created_at"]) not in {"current_timestamp", "now"}:
        raise MigrationValidationError("Target activity timestamp default is incompatible")

    # PostgreSQL marks unvalidated constraints and disabled FK triggers in its
    # catalogs. Refuse either state before import.
    status = connection.execute(text("""
        SELECT count(*), count(*) FILTER (WHERE c.convalidated)
        FROM pg_constraint c
        JOIN pg_class child ON child.oid = c.conrelid
        JOIN pg_namespace ns ON ns.oid = child.relnamespace
        WHERE c.contype = 'f' AND ns.nspname = current_schema()
          AND child.relname = ANY(:tables)
    """), {"tables": list(RELATIONSHIPS)}).one()
    if status[0] != len(RELATIONSHIPS) or status[1] != len(RELATIONSHIPS):
        raise MigrationValidationError("Target foreign-key constraints are not validated")
    disabled = connection.execute(text("""
        SELECT count(*) FROM pg_trigger t
        JOIN pg_class child ON child.oid = t.tgrelid
        JOIN pg_namespace ns ON ns.oid = child.relnamespace
        WHERE ns.nspname = current_schema() AND child.relname = ANY(:tables)
          AND t.tgisinternal AND t.tgenabled = 'D'
    """), {"tables": list(RELATIONSHIPS)}).scalar_one()
    if disabled:
        raise MigrationValidationError("Target foreign-key enforcement is disabled")


def _relationship_ids(connection, table: str, source_column: str) -> list[tuple[int, int]]:
    return [
        tuple(row)
        for row in connection.execute(
            text(f'SELECT id, "{source_column}" FROM "{table}" ORDER BY id')
        ).all()
    ]


def _verify_relationships(connection, data: dict[str, list[dict[str, object]]]) -> None:
    for table, (source_column, _, _) in RELATIONSHIPS.items():
        expected = [(int(row["id"]), int(row[source_column])) for row in data[table]]
        actual = _relationship_ids(connection, table, source_column)
        if actual != expected:
            raise MigrationValidationError("Migrated foreign-key relationships did not match the source backup")
    # Foreign-key constraints are also checked by the database at transaction
    # commit; these joins make failures explicit before commit.
    invalid = (
        connection.execute(text("SELECT count(*) FROM documents d LEFT JOIN users u ON u.id=d.owner_id WHERE u.id IS NULL")).scalar_one()
        + connection.execute(text("SELECT count(*) FROM assistant_conversations c LEFT JOIN users u ON u.id=c.owner_id WHERE u.id IS NULL")).scalar_one()
        + connection.execute(text("SELECT count(*) FROM assistant_messages m LEFT JOIN assistant_conversations c ON c.id=m.conversation_id WHERE c.id IS NULL")).scalar_one()
        + connection.execute(text("SELECT count(*) FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id WHERE u.id IS NULL")).scalar_one()
    )
    if invalid:
        raise MigrationValidationError("Migrated foreign-key integrity validation failed")


def _set_and_verify_sequences(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    sequence_names: dict[str, str] = {}
    for table in TABLES:
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"), {"table_name": table}
        ).scalar_one_or_none()
        if not sequence:
            raise MigrationValidationError("Expected PostgreSQL ID sequence was not found")
        sequence_names[table] = sequence
    preparer = connection.dialect.identifier_preparer
    for table, sequence in sequence_names.items():
        maximum = connection.execute(text(f'SELECT max(id) FROM "{table}"')).scalar_one()
        next_value = 1 if maximum is None else maximum + 1
        quoted_sequence = ".".join(preparer.quote(component) for component in sequence.split("."))
        # ALTER SEQUENCE RESTART is transactional in PostgreSQL (unlike
        # setval), so rollback also restores sequence state if validation fails.
        connection.execute(text(f"ALTER SEQUENCE {quoted_sequence} RESTART WITH {int(next_value)}"))
        last_value, is_called = connection.execute(
            text(f"SELECT last_value, is_called FROM {quoted_sequence}")
        ).one()
        if last_value != next_value or is_called is not False:
            raise MigrationValidationError("PostgreSQL ID sequence validation failed")


def _validate_import(connection, data: dict[str, list[dict[str, object]]]) -> None:
    for table in TABLES:
        expected_count = len(data[table])
        actual_count = connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
        if actual_count != expected_count:
            raise MigrationValidationError("Post-import row counts did not match the source backup")
        expected_ids = [int(row["id"]) for row in data[table]]
        actual_ids = [row[0] for row in connection.execute(text(f'SELECT id FROM "{table}" ORDER BY id')).all()]
        if actual_ids != expected_ids:
            raise MigrationValidationError("Post-import primary keys did not match the source backup")
    _verify_relationships(connection, data)


def migrate(
    apply_changes: bool,
    source_backup: Path = DEFAULT_SOURCE_BACKUP,
    target_url: str | None = None,
    local_storage: Path = LOCAL_STORAGE,
) -> None:
    phase = "source loading"
    try:
        data = read_source(Path(source_backup), Path(local_storage))
        phase = "connection setup"
        url = target_url if target_url is not None else migration_database_url()
        engine = create_engine(url, pool_pre_ping=True)
    except Exception as exc:
        if isinstance(exc, MigrationValidationError):
            exc.phase = phase
            raise
        raise MigrationPhaseError(phase, type(exc).__name__) from None
    try:
        # Preflight, inserts, and all post-import validations share this one
        # transaction in apply mode, so any exception rolls the import back.
        phase = "connection setup"
        with engine.begin() as connection:
            phase = "target preflight"
            _target_preflight(connection)
            if not apply_changes:
                print("Dry run passed: source integrity/schema/files, target revision/schema/emptiness validated.")
                return
            metadata = MetaData()
            for table_name in TABLES:
                rows = data[table_name]
                if rows:
                    phase = f"inserts ({table_name})"
                    table = Table(table_name, metadata, autoload_with=connection)
                    connection.execute(table.insert(), rows)
            phase = "post-insert validation"
            _validate_import(connection, data)
            phase = "sequence reset"
            _set_and_verify_sequences(connection)
            phase = "transaction commit"
        phase = "completion reporting"
        print("Migration completed; row counts, IDs, relationships, and sequences validated.")
    except MigrationValidationError as exc:
        exc.phase = phase
        raise
    except Exception as exc:
        raise MigrationPhaseError(phase, type(exc).__name__) from None
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-backup",
        type=Path,
        default=DEFAULT_SOURCE_BACKUP,
        help="Backup directory (containing vertex_docs.db and storage/) or SQLite backup file",
    )
    parser.add_argument("--apply", action="store_true", help="Import into the already-migrated empty target")
    args = parser.parse_args()
    try:
        migrate(args.apply, source_backup=args.source_backup)
    except Exception as exc:
        safe_error(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
