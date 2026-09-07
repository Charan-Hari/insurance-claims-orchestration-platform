import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from claims_service.auth.jwt import CurrentUser
from claims_service.models.audit import AuditRecord
from claims_service.models.claim import ClaimStatus
from claims_service.models.claim import Claim
from claims_service.schemas.claim import ClaimCreate
from claims_service.services import policy_client


class InvalidStatusTransition(ValueError):
    """Raised when a claim status change is outside the allowed lifecycle."""


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


async def create_claim(
    session: AsyncSession,
    claim_data: ClaimCreate,
    authorization: str | None,
) -> Claim:
    await policy_client.get_policy(claim_data.policy_id, authorization)
    claim = Claim(**claim_data.model_dump(), status=ClaimStatus.SUBMITTED)
    session.add(claim)
    await session.commit()
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
    # Keycloak's JWT subject is assumed to be the policyholder ID.
    return "customer" in user.roles and str(claim.policyholder_id) == user.subject


def can_view_policyholder(policyholder_id: uuid.UUID, user: CurrentUser) -> bool:
    return bool(user.roles.intersection({"admin", "agent", "adjuster"})) or (
        "customer" in user.roles and str(policyholder_id) == user.subject
    )