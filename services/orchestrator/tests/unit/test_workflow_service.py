import uuid
from datetime import date
from decimal import Decimal

from orchestrator.schemas.workflow import ClaimWorkflowCreate, WorkflowState
from orchestrator.services.workflow_service import request_fingerprint


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
