import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from policy_service.auth.jwt import CurrentUser
from policy_service.models.audit import AuditRecord
from policy_service.models.policy import PolicyStatus
from policy_service.models.policy import Policy
from policy_service.schemas.policy import PolicyCreate


class InvalidStatusTransition(ValueError):
    """Raised when a policy status change is outside the allowed lifecycle."""


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


async def get_policy_by_id(session: AsyncSession, policy_id: uuid.UUID) -> Policy | None:
    return await session.get(Policy, policy_id)


async def list_policies_for_policyholder(session: AsyncSession, policyholder_id: uuid.UUID) -> list[Policy]:
    result = await session.execute(select(Policy).where(Policy.policyholder_id == policyholder_id))
    return list(result.scalars().all())


async def update_policy_status(
    session: AsyncSession,
    policy_id: uuid.UUID,
    target_status: PolicyStatus,
    actor_id: str,
) -> Policy | None:
    policy = await session.get(Policy, policy_id)
    if policy is None:
        return None

    old_status = policy.status
    if not is_valid_status_transition(old_status, target_status):
        raise InvalidStatusTransition(f"Invalid status transition: {old_status.value} -> {target_status.value}")

    try:
        policy.status = target_status
        session.add(
            AuditRecord(
                policy_id=policy.id,
                actor_id=actor_id,
                old_status=old_status,
                new_status=target_status,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(policy)
    return policy


def can_view_policy(policy: Policy, user: CurrentUser) -> bool:
    if user.roles.intersection({"admin", "agent", "underwriter"}):
        return True
    # Keycloak's JWT subject is assumed to be the policyholder ID.
    return "customer" in user.roles and str(policy.policyholder_id) == user.subject


def can_view_policyholder(policyholder_id: uuid.UUID, user: CurrentUser) -> bool:
    return bool(user.roles.intersection({"admin", "agent", "underwriter"})) or (
        "customer" in user.roles and str(policyholder_id) == user.subject
    )