from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from copilot_rag.generator import HostedGenerator, build_generator, generate_with_fallback

DISCLAIMER = "This is an assistive draft, not an adjudication or coverage decision. A qualified human must review and approve it."


def database_path() -> Path:
    path = Path(os.getenv("COPILOT_RAG_DB_PATH", "/var/lib/copilot-rag/copilot-rag.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
        policy_id TEXT, claim_id TEXT, source TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY, question TEXT NOT NULL, policy_id TEXT, claim_id TEXT,
        answer TEXT NOT NULL, citations TEXT NOT NULL, status TEXT NOT NULL,
        reviewed_by TEXT, reviewer_note TEXT, created_at TEXT NOT NULL, decided_at TEXT)""")
    # Generator provenance was added after the initial schema; existing databases are
    # migrated in place so a redeploy does not lose previously recorded drafts.
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
    if "generator" not in existing:
        conn.execute("ALTER TABLE drafts ADD COLUMN generator TEXT NOT NULL DEFAULT 'deterministic'")
    if "degraded" not in existing:
        conn.execute("ALTER TABLE drafts ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)
    policy_id: str | None = Field(default=None, max_length=128)
    claim_id: str | None = Field(default=None, max_length=128)
    source: str = Field(default="local", max_length=200)


class DraftIn(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    policy_id: str | None = Field(default=None, max_length=128)
    claim_id: str | None = Field(default=None, max_length=128)
    top_k: int = Field(default=3, ge=1, le=10)


class ApprovalIn(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=2_000)


def require_auth(
    x_api_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    expected = os.getenv("COPILOT_RAG_API_KEY", "local-development-key")
    supplied = x_api_key
    if supplied is None and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not expected or supplied != expected:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return "api-client"


def row_knowledge(row: sqlite3.Row) -> dict:
    return dict(row)


def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{2,}", value.lower())}


def retrieve(question: str, policy_id: str | None, claim_id: str | None, limit: int) -> list[dict]:
    query_tokens = tokens(question)
    with db() as conn:
        rows = conn.execute("SELECT * FROM knowledge ORDER BY created_at DESC").fetchall()
    scored = []
    for row in rows:
        if policy_id and row["policy_id"] not in (None, policy_id):
            continue
        if claim_id and row["claim_id"] not in (None, claim_id):
            continue
        score = len(query_tokens & tokens(row["title"] + " " + row["content"]))
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1]["created_at"], item[1]["id"]))
    return [{**row_knowledge(row), "score": score} for score, row in scored[:limit]]


app = FastAPI(title="Copilot/RAG Service", version="0.1.0")
app.add_middleware(RequestIdMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/readiness")
def readiness():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(503, "Storage is unavailable") from exc


@app.post("/knowledge", status_code=201)
def ingest(document: KnowledgeIn, _: str = Depends(require_auth)):
    document_id = str(uuid.uuid4())
    created = now()
    with db() as conn:
        conn.execute("INSERT INTO knowledge VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (document_id, document.title, document.content, document.policy_id,
                      document.claim_id, document.source, created))
    return {"id": document_id, **document.model_dump(), "created_at": created}


@app.post("/knowledge/upload", status_code=201)
async def ingest_upload(
    file: UploadFile = File(...),
    policy_id: str | None = Query(default=None, max_length=128),
    claim_id: str | None = Query(default=None, max_length=128),
    _: str = Depends(require_auth),
):
    content = await file.read(200_001)
    if not content or len(content) > 200_000:
        raise HTTPException(413, "File must contain between 1 and 200000 bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(415, "Only UTF-8 text files are supported") from exc
    return ingest(KnowledgeIn(title=Path(file.filename or "document").name, content=text,
                              policy_id=policy_id, claim_id=claim_id, source="upload"), _)


@app.get("/retrieve")
def retrieve_endpoint(
    q: str = Query(min_length=1, max_length=2_000),
    policy_id: str | None = None,
    claim_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    _: str = Depends(require_auth),
):
    return {"results": retrieve(q, policy_id, claim_id, limit)}


@app.post("/drafts", status_code=201)
def create_draft(request: DraftIn, _: str = Depends(require_auth)):
    matches = retrieve(request.question, request.policy_id, request.claim_id, request.top_k)
    result = generate_with_fallback(build_generator(), request.question, matches)
    draft_id = str(uuid.uuid4())
    citations = [{"knowledge_id": item["id"], "title": item["title"], "score": item["score"],
                  "source": item["source"]} for item in matches]
    created = now()
    with db() as conn:
        conn.execute(
            """INSERT INTO drafts (id, question, policy_id, claim_id, answer, citations,
               status, reviewed_by, reviewer_note, created_at, decided_at, generator, degraded)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, NULL, ?, ?)""",
            (draft_id, request.question, request.policy_id, request.claim_id,
             result.answer, repr(citations), created, result.provider, int(result.degraded)))
    return {"id": draft_id, "question": request.question, "answer": result.answer,
            "citations": citations, "disclaimer": DISCLAIMER, "approval_required": True,
            "status": "pending", "created_at": created, "generator": result.provider,
            "degraded": result.degraded, "degraded_reason": result.degraded_reason}


@app.post("/drafts/{draft_id}/approval")
def approve_draft(draft_id: str, decision: ApprovalIn, principal: str = Depends(require_auth)):
    with db() as conn:
        row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Draft not found")
        if row["status"] != "pending":
            raise HTTPException(409, "Draft has already been decided")
        decided = now()
        status_value = "approved" if decision.approved else "rejected"
        conn.execute("UPDATE drafts SET status=?, reviewed_by=?, reviewer_note=?, decided_at=? WHERE id=?",
                     (status_value, principal, decision.note, decided, draft_id))
    return {"id": draft_id, "status": status_value, "reviewed_by": principal,
            "reviewer_note": decision.note, "decided_at": decided,
            "disclaimer": DISCLAIMER}
