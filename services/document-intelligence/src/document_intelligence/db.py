import sqlite3
from pathlib import Path

from .config import database_path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, claim_id TEXT, policy_id TEXT,
  original_filename TEXT NOT NULL, media_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL,
  storage_name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
  uploaded_by TEXT NOT NULL, metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_checksum_idx ON documents(checksum_sha256);
CREATE INDEX IF NOT EXISTS documents_search_idx ON documents(claim_id, policy_id);
CREATE TABLE IF NOT EXISTS idempotency (
  key TEXT PRIMARY KEY, request_fingerprint TEXT NOT NULL,
  document_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
  recommendation TEXT NOT NULL, confidence TEXT NOT NULL,
  reasons_json TEXT NOT NULL, status TEXT NOT NULL,
  reviewed_by TEXT, reviewer_note TEXT, created_at TEXT NOT NULL,
  decided_at TEXT
);
"""


def initialize() -> None:
    with connect() as db:
        db.executescript(SCHEMA)
