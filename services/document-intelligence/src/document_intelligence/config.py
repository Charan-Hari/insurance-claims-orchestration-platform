import os
from pathlib import Path


def storage_path() -> Path:
    path = Path(os.getenv("DOCUMENT_STORAGE_PATH", "/var/lib/document-intelligence"))
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def database_path() -> Path:
    return storage_path() / "document-intelligence.sqlite3"


def api_key() -> str:
    return os.getenv("DOCUMENT_INTELLIGENCE_API_KEY", "local-development-key")


def max_upload_bytes() -> int:
    return int(os.getenv("DOCUMENT_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
