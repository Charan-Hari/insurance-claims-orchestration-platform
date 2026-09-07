from sqlalchemy.ext.asyncio import AsyncSession

from policy_service.models.policy import PolicyStatus
from policy_service.models.policy import Policy
from policy_service.schemas.policy import PolicyCreate


VALID_STATUS_TRANSITIONS: dict[PolicyStatus, frozenset[PolicyStatus]] = {
    PolicyStatus.DRAFT: frozenset({PolicyStatus.PENDING_UNDERWRITING}),
    PolicyStatus.PENDING_UNDERWRITING: frozenset({PolicyStatus.ACTIVE}),
    PolicyStatus.ACTIVE: frozenset({PolicyStatus.CANCELLED, PolicyStatus.EXPIRED, PolicyStatus.RENEWED}),
    PolicyStatus.CANCELLED: frozenset(),
    PolicyStatus.EXPIRED: frozenset({PolicyStatus.RENEWED}),
    PolicyStatus.RENEWED: frozenset({PolicyStatus.PENDING_UNDERWRITING}),
}


def is_valid_status_transition(current: PolicyStatus, target: PolicyStatus) -> bool:
    return target in VALID_STATUS_TRANSITIONS[current]


async def create_policy(session: AsyncSession, policy_data: PolicyCreate) -> Policy:
    policy = Policy(**policy_data.model_dump(), status=PolicyStatus.DRAFT)
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy