import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from policy_service.models.audit import AuditRecord
from policy_service.models.policy import Policy, PolicyStatus
from policy_service.services.policy_service import (
    InvalidStatusTransition,
    VALID_STATUS_TRANSITIONS,
    is_valid_status_transition,
    update_policy_status,
)


def make_policy(status: PolicyStatus) -> Policy:
    return Policy(
        id=uuid.uuid4(),
        policyholder_id=uuid.uuid4(),
        coverage_type="property",
        coverage_limits={"dwelling": 250000},
        effective_date=date(2026, 10, 1),
        expiry_date=date(2027, 10, 1),
        status=status,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current, targets in VALID_STATUS_TRANSITIONS.items()
        for target in targets
    ],
)
def test_valid_status_transitions_are_allowed(current: PolicyStatus, target: PolicyStatus) -> None:
    assert is_valid_status_transition(current, target)


@pytest.mark.asyncio
async def test_invalid_transition_does_not_mutate_or_write_audit() -> None:
    policy = make_policy(PolicyStatus.ACTIVE)
    session = MagicMock()
    session.get = AsyncMock(return_value=policy)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    with pytest.raises(InvalidStatusTransition, match="active -> draft"):
        await update_policy_status(session, policy.id, PolicyStatus.DRAFT, "underwriter-1")

    assert policy.status is PolicyStatus.ACTIVE
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_transition_updates_policy_and_adds_audit_record_atomically() -> None:
    policy = make_policy(PolicyStatus.DRAFT)
    session = MagicMock()
    session.get = AsyncMock(return_value=policy)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    updated = await update_policy_status(session, policy.id, PolicyStatus.PENDING_UNDERWRITING, "underwriter-1")

    assert updated is policy
    assert policy.status is PolicyStatus.PENDING_UNDERWRITING
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditRecord)
    assert audit.policy_id == policy.id
    assert audit.actor_id == "underwriter-1"
    assert audit.old_status is PolicyStatus.DRAFT
    assert audit.new_status is PolicyStatus.PENDING_UNDERWRITING
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_insert_failure_rolls_back_status_update() -> None:
    policy = make_policy(PolicyStatus.DRAFT)
    session = MagicMock()
    session.get = AsyncMock(return_value=policy)
    session.add.side_effect = RuntimeError("audit insert failed")
    session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="audit insert failed"):
        await update_policy_status(session, policy.id, PolicyStatus.PENDING_UNDERWRITING, "underwriter-1")

    assert policy.status is PolicyStatus.PENDING_UNDERWRITING
    session.rollback.assert_awaited_once()
