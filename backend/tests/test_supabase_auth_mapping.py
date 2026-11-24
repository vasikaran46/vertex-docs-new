"""Local checks for the additive Supabase Auth identity mapping revision."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Uuid, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20261117_03_supabase_auth_mapping.py"
)
PASSWORD_MIGRATION_PATH = MIGRATION_PATH.with_name("20261117_04_supabase_passwordless_profiles.py")
SPEC = importlib.util.spec_from_file_location("supabase_auth_mapping", MIGRATION_PATH)
MIGRATION = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MIGRATION)
PASSWORD_SPEC = importlib.util.spec_from_file_location("supabase_passwordless_profiles", PASSWORD_MIGRATION_PATH)
PASSWORD_MIGRATION = importlib.util.module_from_spec(PASSWORD_SPEC)
assert PASSWORD_SPEC and PASSWORD_SPEC.loader
PASSWORD_SPEC.loader.exec_module(PASSWORD_MIGRATION)


class SupabaseAuthMappingTests(unittest.TestCase):
    def test_model_mapping_is_nullable_unique_uuid(self):
        column = User.__table__.c.supabase_auth_id
        self.assertIsInstance(column.type, Uuid)
        self.assertFalse(column.type.as_uuid)
        self.assertTrue(column.nullable)
        self.assertTrue(any(index.unique and [column.name for column in index.columns] == ["supabase_auth_id"]
                            for index in User.__table__.indexes))

    def test_legacy_user_reads_do_not_select_new_mapping_column(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = create_engine(f"sqlite:///{(Path(temporary) / 'legacy.db').as_posix()}")
            try:
                with engine.begin() as connection:
                    connection.execute(text("""
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL,
                            email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL,
                            theme VARCHAR(24) NOT NULL, language VARCHAR(20) NOT NULL,
                            avatar VARCHAR(80) NOT NULL
                        )
                    """))
                    connection.execute(text("""
                        INSERT INTO users VALUES (5, 'Legacy', 'legacy@example.invalid', 'hash', 'theme', 'en', 'pip')
                    """))
                with Session(engine) as session:
                    self.assertEqual(session.get(User, 5).email, "legacy@example.invalid")
                    session.add(User(
                        name="New Legacy User", email="new-legacy@example.invalid",
                        password_hash="hash", theme="theme", language="en", avatar="pip",
                    ))
                    session.commit()
            finally:
                engine.dispose()

    def test_sqlite_revision_preserves_users_and_is_admin(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "auth-mapping.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with engine.begin() as connection:
                    connection.execute(text("""
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY,
                            name VARCHAR(120) NOT NULL,
                            email VARCHAR(255) NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            theme VARCHAR(24) NOT NULL,
                            language VARCHAR(20) NOT NULL,
                            avatar VARCHAR(80) NOT NULL,
                            is_admin BOOLEAN NOT NULL DEFAULT 0
                        )
                    """))
                    connection.execute(text("""
                        INSERT INTO users (id, name, email, password_hash, theme, language, avatar, is_admin)
                        VALUES (4, 'Existing Admin', 'admin@example.invalid', 'hash-a', 'theme', 'en', 'pip', 1),
                               (9, 'Existing User', 'user@example.invalid', 'hash-b', 'theme', 'en', 'pip', 0)
                    """))
                    context = MigrationContext.configure(connection)
                    with Operations.context(context):
                        MIGRATION.upgrade()
                        PASSWORD_MIGRATION.upgrade()

                    rows = connection.execute(
                        text("SELECT id, is_admin, supabase_auth_id FROM users ORDER BY id")
                    ).all()
                    self.assertEqual([(row.id, row.is_admin) for row in rows], [(4, 1), (9, 0)])
                    self.assertEqual([row.supabase_auth_id for row in rows], [None, None])
                    indexes = inspect(connection).get_indexes("users")
                    self.assertTrue(any(
                        index["name"] == "ix_users_supabase_auth_id" and index["unique"]
                        for index in indexes
                    ))
                    password_column = next(
                        column for column in inspect(connection).get_columns("users")
                        if column["name"] == "password_hash"
                    )
                    self.assertTrue(password_column["nullable"])

                    # Multiple existing/unlinked accounts may keep a NULL value;
                    # populated mappings remain unique.
                    connection.execute(text("""
                        INSERT INTO users (id, name, email, password_hash, theme, language, avatar)
                        VALUES (10, 'New User', 'new@example.invalid', 'hash-c', 'theme', 'en', 'pip')
                    """))
                    self.assertEqual(
                        connection.execute(text("SELECT is_admin FROM users WHERE id=10")).scalar_one(),
                        0,
                    )
                    connection.execute(
                        text("UPDATE users SET supabase_auth_id=:uuid WHERE id=4"),
                        {"uuid": "38fb93f1-2a58-4c5c-9be7-f069e836f69c"},
                    )
                    with self.assertRaises(IntegrityError):
                        connection.execute(
                            text("UPDATE users SET supabase_auth_id=:uuid WHERE id=9"),
                            {"uuid": "38fb93f1-2a58-4c5c-9be7-f069e836f69c"},
                        )
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
