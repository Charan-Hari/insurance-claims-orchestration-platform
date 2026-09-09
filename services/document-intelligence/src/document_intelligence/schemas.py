from datetime import datetime
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    id: str
    claim_id: str | None = None
    policy_id: str | None = None
    original_filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentSearchResult(DocumentMetadata):
    pass


class ReviewResponse(BaseModel):
    id: str
    document_id: str
    recommendation: str
    confidence: str
    reasons: list[str]
    status: str
    reviewed_by: str | None = None
    reviewer_note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=2000)
