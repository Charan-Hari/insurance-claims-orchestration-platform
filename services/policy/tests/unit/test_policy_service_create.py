import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from policy_service.models.policy import Policy, PolicyStatus
from policy_service.schemas.policy import PolicyCreate
from policy_service.services.policy_service import create_policy


def policy_payload() -> PolicyCreate:
    return PolicyCreate(
        policyholder_id=uuid.uuid4(),
        coverage_type="property",
        coverage_limits={"dwelling": 250000},
        effective_date=date(2026, 10, 1),
        expiry_date=date(2027, 10, 1),
        premium_amount=Decimal("1200.00"),
    )


@pytest.mark.asyncio
async def test_create_policy_defaults_to_draft_and_persists() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    payload = policy_payload()

    policy = await create_policy(session, payload)

    assert isinstance(policy, Policy)
    assert policy.status is PolicyStatus.DRAFT
    assert policy.policyholder_id == payload.policyholder_id
    assert policy.coverage_limits == payload.coverage_limits
    session.add.assert_called_once_with(policy)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(policy)


def test_create_policy_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        PolicyCreate(
            coverage_type="property",
            coverage_limits={"dwelling": 250000},
            effective_date=date(2026, 10, 1),
            expiry_date=date(2027, 10, 1),
        )