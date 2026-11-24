"""Focused local tests for the dry-run SQLite snapshot importer."""

from __future__ import annotations

import sqlite3
import hashlib
import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts import migrate_sqlite_to_supabase as migration_tool
from scripts.migrate_sqlite_to_supabase import MigrationValidationError, TABLES, migrate, read_source


def configured_local_postgres_url():
    raw = os.environ.get("VERTEX_MIGRATION_TEST_DATABASE_URL")
    if not raw:
        return None
    url = make_url(raw)
    # A dedicated opt-in local test database only. Never allow a Supabase or
    # other remote host, and require an unmistakably test-only database name.
    if (url.drivername not in {"postgresql", "postgresql+psycopg"}
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or "test" not in (url.database or "").lower()):
        raise RuntimeError("PostgreSQL integration URL must point to a local test database")
    return url


POSTGRES_TEST_URL = configured_local_postgres_url()


SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, theme VARCHAR(24), language VARCHAR(20),
    avatar VARCHAR(80), is_admin BOOLEAN NOT NULL DEFAULT 0
);
CREATE TABLE documents (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
    original_name VARCHAR(255) NOT NULL, stored_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(120) NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE assistant_conversations (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(120) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE assistant_messages (
    id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL, content TEXT NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL, entity_id INTEGER, metadata JSON NOT NULL DEFAULT '{}', created_at DATETIME NOT NULL
);
"""


def create_snapshot(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "storage").mkdir()
    (directory / "storage" / "upload.pdf").write_bytes(b"fixture PDF bytes")
    database = directory / "vertex_docs.db"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    connection.executescript(
        """
        CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
        INSERT INTO alembic_version VALUES ('20261117_02');
        INSERT INTO users VALUES (7, 'Test User', 'private@example.invalid', 'hash', 'theme', 'en', 'avatar', 1);
        INSERT INTO documents VALUES (11, 7, 'private.pdf', 'upload.pdf', 'application/pdf', 17);
        INSERT INTO assistant_conversations VALUES (13, 7, 'title', '2026-11-17 10:00:00', '2026-11-17 10:01:00');
        INSERT INTO assistant_messages VALUES (17, 13, 'assistant', 'fixture content', '2026-11-17 10:02:00');
        INSERT INTO activity_logs VALUES (19, 7, 'pdf_export', 'document', 11, '{"pages": 1}', '2026-11-17 10:03:00');
        """
    )
    connection.commit()
    connection.close()
    return database


def create_target(path: Path, revision: str = "20261117_02", schema: str = SCHEMA) -> str:
    connection = sqlite3.connect(path)
    connection.executescript(schema)
    connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    connection.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
    connection.commit()
    connection.close()
    return f"sqlite:///{path.as_posix()}"


class SupabaseMigrationToolTests(unittest.TestCase):
    def test_recognizes_postgresql_serial_sequence_defaults(self):
        self.assertTrue(migration_tool._is_sequence_default("nextval('users_id_seq'::regclass)"))
        self.assertTrue(migration_tool._is_sequence_default(" NEXTVAL ( 'public.users_id_seq'::REGCLASS ) "))
        self.assertFalse(migration_tool._is_sequence_default(None))
        self.assertFalse(migration_tool._is_sequence_default("nextval('users_id_seq'::text)"))

    def test_reads_all_five_tables_and_preserves_admin_timestamp_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = create_snapshot(root / "snapshot")
            data = read_source(snapshot, root / "empty-local-storage")
            self.assertEqual(tuple(data), TABLES)
            self.assertEqual([row["id"] for row in data["users"]], [7])
            self.assertEqual(data["users"][0]["is_admin"], 1)
            self.assertEqual(data["assistant_conversations"][0]["created_at"].isoformat(), "2026-11-17T10:00:00")
            self.assertEqual(data["activity_logs"][0]["metadata"], {"pages": 1})

    def test_apply_imports_ids_relationships_and_all_five_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target)
            migrate(True, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            connection = sqlite3.connect(target)
            self.assertEqual(connection.execute("SELECT count(*) FROM users WHERE id=7 AND is_admin=1").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT owner_id FROM documents WHERE id=11").fetchone()[0], 7)
            self.assertEqual(connection.execute("SELECT conversation_id FROM assistant_messages WHERE id=17").fetchone()[0], 13)
            self.assertEqual(connection.execute("SELECT created_at FROM assistant_conversations WHERE id=13").fetchone()[0], "2026-11-17 10:00:00.000000")
            self.assertEqual(connection.execute("SELECT user_id FROM activity_logs WHERE id=19").fetchone()[0], 7)
            self.assertEqual(connection.execute("SELECT json_extract(metadata, '$.pages') FROM activity_logs").fetchone()[0], 1)
            self.assertEqual([connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES], [1] * 5)
            connection.close()

    def test_dry_run_leaves_target_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target)
            migrate(False, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            connection = sqlite3.connect(target)
            self.assertEqual([connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES], [0] * 5)
            connection.close()

    def test_dry_run_leaves_backup_database_and_storage_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target)
            stored_file = snapshot.parent / "storage" / "upload.pdf"
            before = {p: hashlib.sha256(p.read_bytes()).digest() for p in (snapshot, stored_file, target)}
            migrate(False, snapshot.parent, target_url=target_url, local_storage=root / "empty")
            self.assertEqual({p: hashlib.sha256(p.read_bytes()).digest() for p in before}, before)

    def test_mid_import_failure_rolls_back_every_table(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target)
            with patch.object(migration_tool, "_validate_import", side_effect=MigrationValidationError("simulated failure")):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    migrate(True, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual([connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES], [0] * 5)

    def test_database_error_details_are_suppressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            secret_text = "postgresql://user:private-password@host/db"
            with patch.object(migration_tool, "create_engine", side_effect=RuntimeError(secret_text)):
                with self.assertRaises(RuntimeError) as raised:
                    migrate(False, root / "snapshot", target_url=secret_text, local_storage=root / "empty")
            self.assertNotIn("private-password", str(raised.exception))
            self.assertNotIn("postgresql://", str(raised.exception))

    def test_rejects_wrong_target_revision_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target, revision="20261117_01")
            with self.assertRaisesRegex(RuntimeError, "revision"):
                migrate(True, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            connection = sqlite3.connect(target)
            self.assertEqual(connection.execute("SELECT count(*) FROM users").fetchone()[0], 0)
            connection.close()

    def test_rejects_target_missing_expected_foreign_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            schema_without_activity_fk = SCHEMA.replace(
                "user_id INTEGER NOT NULL REFERENCES users(id)",
                "user_id INTEGER NOT NULL",
            )
            target_url = create_target(target, schema=schema_without_activity_fk)
            with self.assertRaisesRegex(MigrationValidationError, "foreign-key"):
                migrate(True, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual(
                    [connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES],
                    [0] * 5,
                )


    def test_refuses_nonempty_target_without_duplicate_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_snapshot(root / "snapshot")
            target = root / "target.db"
            target_url = create_target(target)
            with closing(sqlite3.connect(target)) as connection:
                connection.execute("INSERT INTO users VALUES (99, 'target', 'target@example.invalid', 'hash', 'theme', 'en', 'avatar', 0)")
                connection.commit()
            with self.assertRaisesRegex(RuntimeError, "not empty"):
                migrate(True, root / "snapshot", target_url=target_url, local_storage=root / "empty")
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual(connection.execute("SELECT id FROM users").fetchall(), [(99,)])


@unittest.skipUnless(POSTGRES_TEST_URL, "Set VERTEX_MIGRATION_TEST_DATABASE_URL to an isolated local test database")
class PostgresMigrationIntegrationTests(unittest.TestCase):
    def test_sequences_advance_and_foreign_keys_are_enforced(self):
        import uuid

        schema = "migration_test_" + uuid.uuid4().hex
        base_engine = create_engine(POSTGRES_TEST_URL)
        target_engine = None
        try:
            with base_engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            url = POSTGRES_TEST_URL
            options = url.query.get("options", "")
            scoped_url = url.set(query={**url.query, "options": f"{options} -csearch_path={schema}".strip()})
            target_engine = create_engine(scoped_url)
            with target_engine.begin() as connection:
                ddl = [
                    "CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY NOT NULL)",
                    "INSERT INTO alembic_version VALUES ('20261117_02')",
                    "CREATE TABLE users (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, name varchar(120) NOT NULL, email varchar(255) NOT NULL, password_hash varchar(255) NOT NULL, theme varchar(24) NOT NULL, language varchar(20) NOT NULL, avatar varchar(80) NOT NULL, is_admin boolean NOT NULL DEFAULT false, UNIQUE(email))",
                    "CREATE TABLE documents (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, owner_id integer NOT NULL REFERENCES users(id), original_name varchar(255) NOT NULL, stored_name varchar(255) NOT NULL UNIQUE, content_type varchar(120) NOT NULL, size integer NOT NULL)",
                    "CREATE TABLE assistant_conversations (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, owner_id integer NOT NULL REFERENCES users(id), title varchar(120) NOT NULL, created_at timestamp NOT NULL, updated_at timestamp NOT NULL)",
                    "CREATE TABLE assistant_messages (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, conversation_id integer NOT NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE, role varchar(16) NOT NULL, content text NOT NULL, created_at timestamp NOT NULL)",
                    "CREATE TABLE activity_logs (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id), action varchar(80) NOT NULL, entity_type varchar(80) NOT NULL, entity_id integer, metadata json NOT NULL DEFAULT '{}'::json, created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)",
                ]
                for statement in ddl:
                    connection.execute(text(statement))
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                snapshot = create_snapshot(root / "snapshot")
                # Ensure explicit, non-contiguous source IDs exercise every reset.
                migrate(True, snapshot.parent, target_url=scoped_url.render_as_string(hide_password=False), local_storage=root / "empty")
            with target_engine.begin() as connection:
                user_id = connection.execute(text("INSERT INTO users (name, email, password_hash, theme, language, avatar) VALUES ('Generated', 'generated@example.invalid', 'hash', 'theme', 'en', 'avatar') RETURNING id")).scalar_one()
                document_id = connection.execute(text("INSERT INTO documents (owner_id, original_name, stored_name, content_type, size) VALUES (:owner, 'generated.pdf', 'generated.pdf', 'application/pdf', 1) RETURNING id"), {"owner": user_id}).scalar_one()
                conversation_id = connection.execute(text("INSERT INTO assistant_conversations (owner_id, title, created_at, updated_at) VALUES (7, 'generated', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id")).scalar_one()
                message_id = connection.execute(text("INSERT INTO assistant_messages (conversation_id, role, content, created_at) VALUES (13, 'assistant', 'generated', CURRENT_TIMESTAMP) RETURNING id")).scalar_one()
                activity_id = connection.execute(text("INSERT INTO activity_logs (user_id, action, entity_type) VALUES (7, 'generated', 'test') RETURNING id")).scalar_one()
                self.assertEqual({"users": user_id, "documents": document_id, "assistant_conversations": conversation_id, "assistant_messages": message_id, "activity_logs": activity_id}, {"users": 8, "documents": 12, "assistant_conversations": 14, "assistant_messages": 18, "activity_logs": 20})
                with self.assertRaises(Exception):
                    connection.execute(text("INSERT INTO documents (owner_id, original_name, stored_name, content_type, size) VALUES (999999, 'x', 'bad.pdf', 'application/pdf', 1)"))
        finally:
            if target_engine is not None:
                target_engine.dispose()
            with base_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            base_engine.dispose()

if __name__ == "__main__":
    unittest.main()
