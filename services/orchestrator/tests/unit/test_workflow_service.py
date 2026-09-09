import uuid
from datetime import date
from decimal import Decimal

import pytest

from orchestrator.models import Workflow, WorkflowStep
from orchestrator.schemas.workflow import ClaimWorkflowCreate, WorkflowState
from orchestrator.schemas.workflow import StepState
from orchestrator.services import claims_client, policy_client
from orchestrator.services.workflow_service import _execute_workflow
from orchestrator.services.workflow_service import MAX_RETRY_COUNT, request_fingerprint


def workflow_payload(description: str = "Water damage") -> ClaimWorkflowCreate:
    return ClaimWorkflowCreate(
        policy_id=uuid.uuid4(),
        policyholder_id=uuid.uuid4(),
        claim_amount=Decimal("1250.00"),
        incident_date=date.today(),
        description=description,
    )


def test_request_fingerprint_is_deterministic() -> None:
    payload = workflow_payload()

    assert request_fingerprint(payload) == request_fingerprint(payload)


def test_request_fingerprint_changes_when_request_changes() -> None:
    assert request_fingerprint(workflow_payload("Damage")) != request_fingerprint(
        workflow_payload("Different damage")
    )


def test_workflow_state_enum_contains_required_states() -> None:
    assert WorkflowState.PENDING.value == "pending"
    assert WorkflowState.COMPLETED.value == "completed"
    assert WorkflowState.FAILED.value == "failed"
    assert WorkflowState.RECONCILIATION_REQUIRED.value == "reconciliation_required"


def test_retry_limit_is_bounded() -> None:
    assert MAX_RETRY_COUNT == 3


class RecordingSession:
    def __init__(self) -> None:
        self.events = []

    def add(self, item) -> None:
        self.events.append(item)


def workflow() -> Workflow:
    result = Workflow(
        id=uuid.uuid4(),
        policy_id=uuid.uuid4(),
        policyholder_id=uuid.uuid4(),
        state=WorkflowState.PENDING,
        steps=[
            WorkflowStep(name="policy_verification", state=StepState.PENDING),
            WorkflowStep(name="claim_submission", state=StepState.PENDING),
        ],
    )
    return result


@pytest.mark.asyncio
async def test_success_records_state_and_step_audit_events(monkeypatch) -> None:
    async def policy(*args):
        return {"id": "policy", "status": "active"}

    async def claim(**kwargs):
        return {"id": str(uuid.uuid4())}

    monkeypatch.setattr(policy_client, "get_policy", policy)
    monkeypatch.setattr(claims_client, "create_claim", claim)
    session = RecordingSession()
    record = workflow()

    await _execute_workflow(session, record, workflow_payload(), None, "key")

    assert record.state == WorkflowState.COMPLETED
    assert all(step.state == StepState.SUCCEEDED for step in record.steps)
    assert [event.event_type for event in session.events] == [
        "step_state_changed",
        "workflow_state_changed",
        "step_state_changed",
        "step_state_changed",
        "workflow_state_changed",
        "workflow_state_changed",
    ]


@pytest.mark.asyncio
async def test_ambiguous_claim_result_requires_reconciliation(monkeypatch) -> None:
    async def policy(*args):
        return {"id": "policy", "status": "active"}

    async def claim(**kwargs):
        raise claims_client.ClaimsServiceReconciliationRequired("lost response")

    monkeypatch.setattr(policy_client, "get_policy", policy)
    monkeypatch.setattr(claims_client, "create_claim", claim)
    session = RecordingSession()
    record = workflow()

    await _execute_workflow(session, record, workflow_payload(), "Bearer redacted", "key")

    assert record.state == WorkflowState.RECONCILIATION_REQUIRED
    assert record.failure_category == "ClaimsServiceReconciliationRequired"
    assert any(event.event_type == "reconciliation_required" for event in session.events)
    assert all("Bearer" not in (event.detail or "") for event in session.events)
