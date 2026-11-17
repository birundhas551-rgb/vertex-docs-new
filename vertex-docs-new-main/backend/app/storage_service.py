import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
from supabase import create_client

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

STORAGE_DIR = Path(
    os.getenv("STORAGE_DIR", str(BACKEND_DIR / "storage"))
).resolve()

BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "user-documents")


@lru_cache(maxsize=1)
def get_storage():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("Supabase Storage configuration is missing")

    return create_client(url, key).storage.from_(BUCKET)


def upload_document(stored_name: str, content: bytes, content_type: str):
    return get_storage().upload(
        stored_name,
        content,
        file_options={
            "content-type": content_type,
            "upsert": "true",
        },
    )


def read_document(stored_name: str) -> bytes:
    try:
        return get_storage().download(stored_name)
    except Exception:
        local_file = STORAGE_DIR / stored_name
        if local_file.is_file():
            return local_file.read_bytes()
        raise FileNotFoundError("Document is unavailable in storage")


def delete_document(stored_name: str):
    get_storage().remove([stored_name])

    local_file = STORAGE_DIR / stored_name
    if local_file.is_file():
        local_file.unlink()
