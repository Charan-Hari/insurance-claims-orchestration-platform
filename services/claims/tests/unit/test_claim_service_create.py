from datetime import date, timedelta
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from claims_service.schemas.claim import ClaimCreate
from claims_service.services import claim_service
from claims_service.services.policy_client import PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable


def claim_payload() -> ClaimCreate:
    return ClaimCreate(
        policy_id=uuid.uuid4(),
        policyholder_id=uuid.uuid4(),
        claim_amount=Decimal("1250.00"),
        incident_date=date.today(),
        description="Water damage",
    )


@pytest.mark.asyncio
async def test_create_claim_calls_policy_client_with_authorization_and_submitted_status() -> None:
    session = AsyncMock()
    session.add = lambda claim: setattr(session, "added_claim", claim)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    payload = claim_payload()
    policy_client_mock = AsyncMock(return_value={"id": str(payload.policy_id), "status": "active"})

    with patch.object(claim_service.policy_client, "get_policy", policy_client_mock):
        claim = await claim_service.create_claim(session, payload, "Bearer caller-token")

    policy_client_mock.assert_awaited_once_with(payload.policy_id, "Bearer caller-token")
    assert claim.status.value == "submitted"
    assert claim.policy_id == payload.policy_id
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(claim)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [PolicyNotFound(), PolicyNotActive(), PolicyServiceUnavailable()])
async def test_create_claim_does_not_persist_when_policy_verification_fails(error: Exception) -> None:
    session = AsyncMock()
    policy_client_mock = AsyncMock(side_effect=error)

    with patch.object(claim_service.policy_client, "get_policy", policy_client_mock):
        with pytest.raises(type(error)):
            await claim_service.create_claim(session, claim_payload(), "Bearer token")

    session.commit.assert_not_awaited()


def test_claim_create_rejects_missing_required_fields_negative_amount_and_future_date() -> None:
    with pytest.raises(ValidationError):
        ClaimCreate(
            policy_id=uuid.uuid4(),
            policyholder_id=uuid.uuid4(),
            claim_amount=Decimal("-1.00"),
            incident_date=date.today(),
            description="Water damage",
        )
    with pytest.raises(ValidationError):
        ClaimCreate(
            policy_id=uuid.uuid4(),
            policyholder_id=uuid.uuid4(),
            claim_amount=Decimal("1.00"),
            incident_date=date.today() + timedelta(days=1),
            description="Water damage",
        )