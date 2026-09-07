from datetime import date
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from claims_service.models.audit import AuditRecord
from claims_service.models.claim import Claim, ClaimStatus
from claims_service.services.claim_service import (
    InvalidStatusTransition,
    VALID_STATUS_TRANSITIONS,
    is_valid_status_transition,
    update_claim_status,
)


def make_claim(status: ClaimStatus) -> Claim:
    return Claim(
        id=uuid.uuid4(),
        policy_id=uuid.uuid4(),
        policyholder_id=uuid.uuid4(),
        claim_amount=100,
        incident_date=date(2026, 1, 1),
        description="Loss",
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
def test_valid_claim_status_transitions_are_allowed(current: ClaimStatus, target: ClaimStatus) -> None:
    assert is_valid_status_transition(current, target)


@pytest.mark.asyncio
async def test_invalid_transition_does_not_mutate_or_write_audit() -> None:
    claim = make_claim(ClaimStatus.SUBMITTED)
    session = MagicMock()
    session.get = AsyncMock(return_value=claim)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    with pytest.raises(InvalidStatusTransition, match="submitted -> paid"):
        await update_claim_status(session, claim.id, ClaimStatus.PAID, "adjuster-1")

    assert claim.status is ClaimStatus.SUBMITTED
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_transition_updates_claim_and_adds_audit_atomically() -> None:
    claim = make_claim(ClaimStatus.SUBMITTED)
    session = MagicMock()
    session.get = AsyncMock(return_value=claim)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    updated = await update_claim_status(session, claim.id, ClaimStatus.UNDER_REVIEW, "adjuster-1")

    assert updated is claim
    assert claim.status is ClaimStatus.UNDER_REVIEW
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditRecord)
    assert audit.claim_id == claim.id
    assert audit.actor_id == "adjuster-1"
    assert audit.old_status is ClaimStatus.SUBMITTED
    assert audit.new_status is ClaimStatus.UNDER_REVIEW
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_insert_failure_rolls_back_claim_update() -> None:
    claim = make_claim(ClaimStatus.SUBMITTED)
    session = MagicMock()
    session.get = AsyncMock(return_value=claim)
    session.add.side_effect = RuntimeError("audit insert failed")
    session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="audit insert failed"):
        await update_claim_status(session, claim.id, ClaimStatus.UNDER_REVIEW, "adjuster-1")

    assert claim.status is ClaimStatus.UNDER_REVIEW
    session.rollback.assert_awaited_once()