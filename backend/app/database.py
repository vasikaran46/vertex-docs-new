import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BACKEND_DIR=Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH=BACKEND_DIR/"vertex_docs.db"

def database_url():
<<<<<<< HEAD
    """Keep the local SQLite file in one place, no matter which folder starts the API."""
=======
    """Resolve local SQLite paths and normalize PostgreSQL URLs for psycopg 3."""
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    url=os.getenv("DATABASE_URL","").strip()
    if not url:
        return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    if url.startswith("sqlite:///"):
        path=url[len("sqlite:///"):]
        if path and path!=":memory:" and not Path(path).is_absolute():
            return f"sqlite:///{(BACKEND_DIR/path).resolve().as_posix()}"
<<<<<<< HEAD
    return url

URL=database_url()
engine=create_engine(URL,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {})
=======
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

URL=database_url()
engine=create_engine(URL,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {},pool_pre_ping=not URL.startswith("sqlite"))
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
