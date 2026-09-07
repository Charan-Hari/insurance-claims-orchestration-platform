import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from policy_service.auth.jwt import CurrentUser
from policy_service.models.policy import Policy, PolicyStatus
from policy_service.services.policy_service import (
    can_view_policy,
    get_policy_by_id,
    list_policies_for_policyholder,
)


def make_policy(policyholder_id: uuid.UUID | None = None) -> Policy:
    return Policy(
        id=uuid.uuid4(),
        policyholder_id=policyholder_id or uuid.uuid4(),
        coverage_type="property",
        coverage_limits={"dwelling": 250000},
        effective_date=date(2026, 10, 1),
        expiry_date=date(2027, 10, 1),
        status=PolicyStatus.DRAFT,
    )


@pytest.mark.asyncio
async def test_get_policy_by_id_returns_policy_and_none_for_missing() -> None:
    policy = make_policy()
    session = AsyncMock()
    session.get.side_effect = [policy, None]

    assert await get_policy_by_id(session, policy.id) is policy
    assert await get_policy_by_id(session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_policies_for_policyholder_returns_matching_policies() -> None:
    policyholder_id = uuid.uuid4()
    policies = [make_policy(policyholder_id), make_policy(policyholder_id)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = policies
    session = AsyncMock()
    session.execute.return_value = result

    assert await list_policies_for_policyholder(session, policyholder_id) == policies


def test_customer_can_view_only_own_policy_but_elevated_roles_can_view_any() -> None:
    own_policy = make_policy(uuid.UUID("11111111-1111-1111-1111-111111111111"))
    other_policy = make_policy(uuid.UUID("22222222-2222-2222-2222-222222222222"))
    customer = CurrentUser(subject=str(own_policy.policyholder_id), roles=frozenset({"customer"}), claims={})

    assert can_view_policy(own_policy, customer)
    assert not can_view_policy(other_policy, customer)
    assert can_view_policy(other_policy, CurrentUser(subject="admin-1", roles=frozenset({"admin"}), claims={}))
    assert can_view_policy(other_policy, CurrentUser(subject="agent-1", roles=frozenset({"agent"}), claims={}))
    assert can_view_policy(
        other_policy,
        CurrentUser(subject="underwriter-1", roles=frozenset({"underwriter"}), claims={}),
    )