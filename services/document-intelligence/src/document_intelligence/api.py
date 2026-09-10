import hashlib
import json
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from .auth import Principal, require_auth
from .config import max_upload_bytes, storage_path
from .db import connect
from .rules import review
from .schemas import ApprovalRequest, DocumentMetadata, DocumentSearchResult, ReviewResponse

router = APIRouter(prefix="/documents", dependencies=[Depends(require_auth)])


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def document_from_row(row) -> dict:
    return {
        "id": row["id"], "claim_id": row["claim_id"], "policy_id": row["policy_id"],
        "original_filename": row["original_filename"], "media_type": row["media_type"],
        "size_bytes": row["size_bytes"], "checksum_sha256": row["checksum_sha256"],
        "created_at": row["created_at"], "metadata": json.loads(row["metadata_json"]),
    }


@router.post("", response_model=DocumentMetadata, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    claim_id: str | None = Query(default=None, max_length=128),
    policy_id: str | None = Query(default=None, max_length=128),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_auth),
):
    content = await file.read(max_upload_bytes() + 1)
    if len(content) > max_upload_bytes():
        raise HTTPException(413, "Document exceeds the configured upload limit")
    if not content:
        raise HTTPException(400, "Document must not be empty")
    filename = Path(file.filename or "document").name
    media_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    checksum = hashlib.sha256(content).hexdigest()
    fingerprint = hashlib.sha256(f"{checksum}:{claim_id}:{policy_id}".encode()).hexdigest()
    with connect() as db:
        if idempotency_key:
            existing = db.execute("SELECT * FROM idempotency WHERE key=?", (idempotency_key,)).fetchone()
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise HTTPException(409, "Idempotency-Key was already used for a different document")
                row = db.execute("SELECT * FROM documents WHERE id=?", (existing["document_id"],)).fetchone()
                return document_from_row(row)
        existing = db.execute(
            "SELECT * FROM documents WHERE checksum_sha256=? AND claim_id IS ? AND policy_id IS ?",
            (checksum, claim_id, policy_id),
        ).fetchone()
        if existing:
            return document_from_row(existing)
        document_id, created = str(uuid.uuid4()), now()
        storage_name = f"{document_id}.bin"
        target = storage_path() / storage_name
        target.write_bytes(content)
        db.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_id, claim_id, policy_id, filename, media_type, len(content), checksum,
             storage_name, created, principal.subject, json.dumps({"source": "local-upload"})),
        )
        if idempotency_key:
            db.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?)", (idempotency_key, fingerprint, document_id, created))
        row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    return document_from_row(row)


@router.get("", response_model=list[DocumentSearchResult])
async def search_documents(
    q: str | None = Query(default=None, max_length=200),
    claim_id: str | None = None,
    policy_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    clauses, values = [], []
    if q:
        clauses.append("(original_filename LIKE ? OR checksum_sha256 LIKE ?)")
        values += [f"%{q}%", f"%{q}%"]
    if claim_id:
        clauses.append("claim_id=?"); values.append(claim_id)
    if policy_id:
        clauses.append("policy_id=?"); values.append(policy_id)
    # B608: clauses are fixed literals; every user value is bound below.
    query = (
        "SELECT * FROM documents"  # nosec B608
        + ((" WHERE " + " AND ".join(clauses)) if clauses else "")
        + " ORDER BY created_at DESC LIMIT ?"
    )
    values.append(limit)
    with connect() as db:
        rows = db.execute(query, values).fetchall()
    return [document_from_row(row) for row in rows]


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    return document_from_row(row)


@router.get("/{document_id}/content")
async def retrieve_document(document_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    target = storage_path() / row["storage_name"]
    if not target.is_file() or target.resolve().parent != storage_path():
        raise HTTPException(503, "Document content is unavailable")
    return FileResponse(target, media_type=row["media_type"], filename=row["original_filename"])


@router.post("/{document_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(document_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        content = (storage_path() / row["storage_name"]).read_bytes()
        result = review(row["original_filename"], row["media_type"], content)
        review_id, created = str(uuid.uuid4()), now()
        db.execute(
            "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, NULL)",
            (review_id, document_id, result.recommendation, result.confidence, json.dumps(result.reasons), created),
        )
        review_row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    return review_from_row(review_row)


def review_from_row(row) -> dict:
    return {**dict(row), "reasons": json.loads(row["reasons_json"]), "created_at": row["created_at"], "decided_at": row["decided_at"]}


@router.get("/{document_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(document_id: str):
    with connect() as db:
        rows = db.execute("SELECT * FROM reviews WHERE document_id=? ORDER BY created_at DESC", (document_id,)).fetchall()
    return [review_from_row(row) for row in rows]


@router.post("/reviews/{review_id}/approval", response_model=ReviewResponse)
async def approve_review(review_id: str, decision: ApprovalRequest, principal: Principal = Depends(require_auth)):
    with connect() as db:
        row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Review not found")
        if row["status"] != "pending":
            raise HTTPException(409, "Review has already been decided")
        decided = now()
        db.execute(
            "UPDATE reviews SET status=?, reviewed_by=?, reviewer_note=?, decided_at=? WHERE id=?",
            ("approved" if decision.approved else "rejected", principal.subject, decision.note, decided, review_id),
        )
        updated = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    return review_from_row(updated)
