from sqlalchemy.ext.asyncio import AsyncSession

from claims_service.models.claim import ClaimStatus
from claims_service.models.claim import Claim
from claims_service.schemas.claim import ClaimCreate
from claims_service.services import policy_client


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