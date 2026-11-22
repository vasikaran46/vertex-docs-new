import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
if not os.getenv("VERTEX_IGNORE_ENV_FILE"):
    load_dotenv(BACKEND_DIR / ".env")

STORAGE_DIR = Path(
    os.getenv("STORAGE_DIR", str(BACKEND_DIR / "storage"))
).resolve()

BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "user-documents")


def supabase_storage_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


@lru_cache(maxsize=1)
def get_storage():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("Supabase Storage configuration is missing")

    from supabase import create_client  # imported lazily so local-only setups still start

    return create_client(url, key).storage.from_(BUCKET)


def _local_path(stored_name: str) -> Path:
    path = (STORAGE_DIR / stored_name).resolve()
    if STORAGE_DIR not in path.parents:
        raise ValueError("Invalid storage path")
    return path


def upload_document(stored_name: str, content: bytes, content_type: str):
    """Save to local disk first; sync to Supabase Storage if configured and working."""
    path = _local_path(stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    if supabase_storage_configured():
        try:
            get_storage().upload(
                stored_name,
                content,
                file_options={
                    "content-type": content_type,
                    "upsert": "true",
                },
            )
        except Exception:
            # Local storage is already preserved safely
            pass
    return {"stored": "local"}


def read_document(stored_name: str) -> bytes:
    local_file = _local_path(stored_name)
    if not supabase_storage_configured():
        if local_file.is_file():
            return local_file.read_bytes()
        raise FileNotFoundError("Document is unavailable in storage")
    try:
        return get_storage().download(stored_name)
    except Exception:
        if local_file.is_file():
            return local_file.read_bytes()
        raise FileNotFoundError("Document is unavailable in storage")


def delete_document(stored_name: str):
    if supabase_storage_configured():
        get_storage().remove([stored_name])
    local_file = _local_path(stored_name)
    if local_file.is_file():
        local_file.unlink()
