import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from legacy_adapter.models.claim import LegacyClaim
from legacy_adapter.schemas.claim import LegacyClaimIn


def fingerprint(record: LegacyClaimIn) -> str:
    payload = record.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def ingest_claim(session: AsyncSession, record: LegacyClaimIn) -> tuple[LegacyClaim, bool]:
    existing = await session.scalar(select(LegacyClaim).where(
        LegacyClaim.source_system == record.source_system,
        LegacyClaim.legacy_claim_id == record.legacy_claim_id,
    ))
    if existing:
        if fingerprint(record) != fingerprint(LegacyClaimIn.model_validate(existing.raw_payload)):
            raise ValueError("Legacy claim ID already exists with different content")
        return existing, False

    values = record.model_dump()
    payload = record.model_dump(mode="json")
    claim = LegacyClaim(**values)
    claim.raw_payload = payload
    session.add(claim)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(LegacyClaim).where(
            LegacyClaim.source_system == record.source_system,
            LegacyClaim.legacy_claim_id == record.legacy_claim_id,
        ))
        if existing is None:
            raise
        if fingerprint(record) != fingerprint(LegacyClaimIn.model_validate(existing.raw_payload)):
            raise ValueError("Legacy claim ID already exists with different content")
        return existing, False
    await session.refresh(claim)
    return claim, True
