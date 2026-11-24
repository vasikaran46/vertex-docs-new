"""Promote one existing local SQLite user during an operator-controlled bootstrap."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True, help="Existing local user ID to promote")
    args = parser.parse_args()
    if args.user_id <= 0:
        parser.error("--user-id must be a positive integer")
    if not sys.stdin.isatty():
        print("Refusing promotion without an interactive operator confirmation.", file=sys.stderr)
        return 2
    expected = f"PROMOTE USER {args.user_id}"
    if input(f"Type {expected!r} to continue: ") != expected:
        print("Promotion cancelled.")
        return 2

    database_path = BACKEND_DIR / "vertex_docs.db"
    if not database_path.is_file():
        print("Refusing: the expected local SQLite database file does not exist.", file=sys.stderr)
        return 5
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            if "alembic_version" not in inspect(connection).get_table_names():
                print("Refusing: the admin foundation migration is not recorded.", file=sys.stderr)
                return 6
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if revision != "20261117_02":
                print("Refusing: the local database is not at the admin foundation revision.", file=sys.stderr)
                return 6
        with Session(engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))
            if session.query(User.id).filter(User.is_admin.is_(True)).first() is not None:
                print("Refusing: an administrator is already assigned.", file=sys.stderr)
                return 3
            user = session.get(User, args.user_id)
            if user is None:
                print("Refusing: the requested local user ID does not exist.", file=sys.stderr)
                return 4
            user.is_admin = True
            session.commit()
        print("The selected existing local user was promoted to administrator.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
