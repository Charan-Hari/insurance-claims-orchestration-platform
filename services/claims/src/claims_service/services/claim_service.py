import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from claims_service.auth.jwt import CurrentUser
from claims_service.models.audit import AuditRecord
from claims_service.models.claim import Claim, ClaimStatus
from claims_service.models.idempotency import ClaimIdempotencyKey
from claims_service.schemas.claim import ClaimCreate
from claims_service.services import policy_client


class InvalidStatusTransition(ValueError):
    """Raised when a claim status change is outside the allowed lifecycle."""


class IdempotencyConflict(ValueError):
    """Raised when a key is reused with a different request."""


class IdempotencyStateError(RuntimeError):
    """Raised when an idempotency record points to missing claim state."""


VALID_STATUS_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.SUBMITTED: frozenset({ClaimStatus.UNDER_REVIEW}),
    ClaimStatus.UNDER_REVIEW: frozenset({ClaimStatus.APPROVED, ClaimStatus.DENIED, ClaimStatus.CLOSED}),
    ClaimStatus.APPROVED: frozenset({ClaimStatus.PAID}),
    ClaimStatus.DENIED: frozenset(),
    ClaimStatus.PAID: frozenset(),
    ClaimStatus.CLOSED: frozenset(),
}


def is_valid_status_transition(current: ClaimStatus, target: ClaimStatus) -> bool:
    return target in VALID_STATUS_TRANSITIONS[current]


def request_fingerprint(claim_data: ClaimCreate) -> str:
    payload = claim_data.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def _existing_idempotent_claim(
    session: AsyncSession,
    subject: str,
    idempotency_key: str,
    fingerprint: str,
) -> Claim | None:
    result = await session.execute(
        select(ClaimIdempotencyKey).where(
            ClaimIdempotencyKey.subject == subject,
            ClaimIdempotencyKey.idempotency_key == idempotency_key,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.request_fingerprint != fingerprint:
        raise IdempotencyConflict("Idempotency-Key was already used with a different request")
    claim = await session.get(Claim, record.claim_id)
    if claim is None:
        raise IdempotencyStateError("Idempotency record references missing claim state")
    return claim


async def create_claim(
    session: AsyncSession,
    claim_data: ClaimCreate,
    authorization: str | None,
    subject: str,
    idempotency_key: str,
) -> Claim:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise ValueError("Idempotency-Key must not be blank")

    fingerprint = request_fingerprint(claim_data)
    existing = await _existing_idempotent_claim(session, subject, normalized_key, fingerprint)
    if existing is not None:
        return existing

    await policy_client.get_policy(claim_data.policy_id, authorization)

    claim = Claim(**claim_data.model_dump(), status=ClaimStatus.SUBMITTED)
    session.add(claim)
    await session.flush()

    session.add(
        ClaimIdempotencyKey(
            subject=subject,
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
            claim_id=claim.id,
        )
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await _existing_idempotent_claim(session, subject, normalized_key, fingerprint)
        if existing is None:
            raise
        return existing

    await session.refresh(claim)
    return claim


async def get_claim_by_id(session: AsyncSession, claim_id: uuid.UUID) -> Claim | None:
    return await session.get(Claim, claim_id)


async def list_claims_for_policyholder(session: AsyncSession, policyholder_id: uuid.UUID) -> list[Claim]:
    result = await session.execute(select(Claim).where(Claim.policyholder_id == policyholder_id))
    return list(result.scalars().all())


async def update_claim_status(
    session: AsyncSession,
    claim_id: uuid.UUID,
    target_status: ClaimStatus,
    actor_id: str,
) -> Claim | None:
    claim = await session.get(Claim, claim_id)
    if claim is None:
        return None

    old_status = claim.status
    if not is_valid_status_transition(old_status, target_status):
        raise InvalidStatusTransition(f"Invalid status transition: {old_status.value} -> {target_status.value}")

    try:
        claim.status = target_status
        session.add(
            AuditRecord(
                claim_id=claim.id,
                actor_id=actor_id,
                old_status=old_status,
                new_status=target_status,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(claim)
    return claim


def can_view_claim(claim: Claim, user: CurrentUser) -> bool:
    if user.roles.intersection({"admin", "agent", "adjuster"}):
        return True
    return "customer" in user.roles and str(claim.policyholder_id) == user.subject


def can_view_policyholder(policyholder_id: uuid.UUID, user: CurrentUser) -> bool:
    return bool(user.roles.intersection({"admin", "agent", "adjuster"})) or (
        "customer" in user.roles and str(policyholder_id) == user.subject
    )
