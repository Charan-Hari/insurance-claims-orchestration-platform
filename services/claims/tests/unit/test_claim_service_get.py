from datetime import date
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from claims_service.auth.jwt import CurrentUser
from claims_service.models.claim import Claim, ClaimStatus
from claims_service.services.claim_service import (
    can_view_claim,
    get_claim_by_id,
    list_claims_for_policyholder,
)


def make_claim(policyholder_id: uuid.UUID | None = None) -> Claim:
    return Claim(
        id=uuid.uuid4(),
        policy_id=uuid.uuid4(),
        policyholder_id=policyholder_id or uuid.uuid4(),
        claim_amount=100,
        incident_date=date(2026, 1, 1),
        description="Loss",
        status=ClaimStatus.SUBMITTED,
    )


@pytest.mark.asyncio
async def test_get_claim_by_id_returns_claim_or_none() -> None:
    claim = make_claim()
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[claim, None])

    assert await get_claim_by_id(session, claim.id) is claim
    assert await get_claim_by_id(session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_claims_for_policyholder_returns_matching_claims() -> None:
    policyholder_id = uuid.uuid4()
    claims = [make_claim(policyholder_id), make_claim(policyholder_id)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = claims
    session = AsyncMock()
    session.execute.return_value = result

    assert await list_claims_for_policyholder(session, policyholder_id) == claims


def test_customer_can_view_only_own_claim_and_elevated_roles_can_view_any() -> None:
    own_claim = make_claim(uuid.UUID("11111111-1111-1111-1111-111111111111"))
    other_claim = make_claim(uuid.UUID("22222222-2222-2222-2222-222222222222"))
    customer = CurrentUser(subject=str(own_claim.policyholder_id), roles=frozenset({"customer"}), claims={})

    assert can_view_claim(own_claim, customer)
    assert not can_view_claim(other_claim, customer)
    for role in ("admin", "agent", "adjuster"):
        assert can_view_claim(other_claim, CurrentUser(subject=f"{role}-1", roles=frozenset({role}), claims={}))