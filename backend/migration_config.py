"""Private configuration helpers for one-off database migration tooling."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parent


def local_sqlite_migration_url() -> str:
    """Return the fixed local SQLite path; this never reads or changes DATABASE_URL."""
    database_path = (BACKEND_DIR / "vertex_docs.db").resolve().as_posix()
    return f"sqlite:///{database_path}"


def migration_database_url() -> str:
    """Read SUPABASE_MIGRATION_URL without changing or displaying environment values."""
    value = os.environ.get("SUPABASE_MIGRATION_URL")
    if not value:
        # Parse only the requested key from backend/.env; never load or override
        # the application's DATABASE_URL.
        env_path = BACKEND_DIR / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, raw = line.partition("=")
                if separator and key.strip() == "SUPABASE_MIGRATION_URL":
                    value = raw.strip().strip("\"'")
                    break
    if not value:
        raise RuntimeError("SUPABASE_MIGRATION_URL is not configured in backend/.env or the process environment")

    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("SUPABASE_MIGRATION_URL must use PostgreSQL")
    return url.render_as_string(hide_password=False)
