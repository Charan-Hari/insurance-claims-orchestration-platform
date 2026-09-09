import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models import (
    Workflow,
    WorkflowAuditEvent,
    WorkflowIdempotencyKey,
    WorkflowStep,
)
from orchestrator.schemas.workflow import (
    ClaimWorkflowCreate,
    StepState,
    WorkflowState,
)
from orchestrator.services import claims_client, policy_client
from orchestrator.services.claims_client import (
    ClaimsServiceRejected,
    ClaimsServiceReconciliationRequired,
    ClaimsServiceUnavailable,
)
from orchestrator.services.policy_client import PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable


class WorkflowConflict(ValueError):
    pass


class WorkflowNotRetryable(ValueError):
    pass


def _audit(
    session: AsyncSession,
    workflow_id: uuid.UUID,
    event_type: str,
    detail: dict | None = None,
) -> None:
    session.add(
        WorkflowAuditEvent(
            workflow_id=workflow_id,
            event_type=event_type,
            detail=json.dumps(detail, sort_keys=True) if detail else None,
        )
    )


def _workflow_state(
    session: AsyncSession,
    workflow: Workflow,
    state: WorkflowState,
    *,
    reason: str | None = None,
) -> None:
    if workflow.state == state:
        return
    old_state = workflow.state
    workflow.state = state
    detail = {"from": old_state.value, "to": state.value}
    if reason:
        detail["reason"] = reason
    _audit(session, workflow.id, "workflow_state_changed", detail)


def _step_state(
    session: AsyncSession,
    workflow: Workflow,
    step: WorkflowStep,
    state: StepState,
    *,
    error_category: str | None = None,
) -> None:
    if step.state == state and step.error_category == error_category:
        return
    old_state = step.state
    step.state = state
    step.error_category = error_category
    _audit(
        session,
        workflow.id,
        "step_state_changed",
        {"step": step.name, "from": old_state.value, "to": state.value, **(
            {"error_category": error_category} if error_category else {}
        )},
    )


def _mark_failure(
    session: AsyncSession,
    workflow: Workflow,
    exc: Exception,
    *,
    reconciliation: bool = False,
) -> None:
    category = type(exc).__name__
    workflow.failure_category = category
    target_state = (
        WorkflowState.RECONCILIATION_REQUIRED if reconciliation else WorkflowState.FAILED
    )
    _workflow_state(session, workflow, target_state, reason=category)
    for index, step in enumerate(workflow.steps):
        if step.state in {StepState.PENDING, StepState.RUNNING}:
            target = StepState.SKIPPED if index else StepState.FAILED
            _step_state(session, workflow, step, target, error_category=category)
    if reconciliation:
        _audit(
            session,
            workflow.id,
            "reconciliation_required",
            {"reason": category, "alert": True},
        )


async def _execute_workflow(
    session: AsyncSession,
    workflow: Workflow,
    data: ClaimWorkflowCreate,
    authorization: str | None,
    idempotency_key: str,
) -> None:
    try:
        await policy_client.get_policy(data.policy_id, authorization)
        _step_state(session, workflow, workflow.steps[0], StepState.SUCCEEDED)
        _workflow_state(session, workflow, WorkflowState.POLICY_VERIFIED)

        _step_state(session, workflow, workflow.steps[1], StepState.RUNNING)
        claim = await claims_client.create_claim(
            policy_id=data.policy_id,
            policyholder_id=data.policyholder_id,
            claim_amount=data.claim_amount,
            incident_date=data.incident_date,
            description=data.description,
            adjuster_notes=data.adjuster_notes,
            authorization=authorization,
            idempotency_key=idempotency_key,
        )
        workflow.claim_id = uuid.UUID(claim["id"])
        _step_state(session, workflow, workflow.steps[1], StepState.SUCCEEDED)
        _workflow_state(session, workflow, WorkflowState.CLAIM_SUBMITTED)
        _workflow_state(session, workflow, WorkflowState.COMPLETED)
        now = datetime.now(timezone.utc)
        for step in workflow.steps:
            step.completed_at = now
    except ClaimsServiceReconciliationRequired as exc:
        _mark_failure(session, workflow, exc, reconciliation=True)
    except (
        ClaimsServiceRejected,
        ClaimsServiceUnavailable,
        PolicyNotActive,
        PolicyNotFound,
        PolicyServiceUnavailable,
    ) as exc:
        _mark_failure(session, workflow, exc)


def request_fingerprint(data: ClaimWorkflowCreate) -> str:
    payload = data.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _find_existing(
    session: AsyncSession,
    subject: str,
    key: str,
    fingerprint: str,
) -> Workflow | None:
    result = await session.execute(
        select(WorkflowIdempotencyKey).where(
            WorkflowIdempotencyKey.subject == subject,
            WorkflowIdempotencyKey.idempotency_key == key,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.request_fingerprint != fingerprint:
        raise WorkflowConflict("Idempotency-Key was already used with a different request")
    return await session.get(Workflow, record.workflow_id)


async def start_claim_workflow(
    session: AsyncSession,
    data: ClaimWorkflowCreate,
    subject: str,
    authorization: str | None,
    idempotency_key: str,
) -> Workflow:
    key = idempotency_key.strip()
    if not key:
        raise ValueError("Idempotency-Key must not be blank")

    fingerprint = request_fingerprint(data)
    existing = await _find_existing(session, subject, key, fingerprint)
    if existing is not None:
        return existing

    workflow = Workflow(
        policy_id=data.policy_id,
        policyholder_id=data.policyholder_id,
        state=WorkflowState.PENDING,
        retry_count=0,
        request_payload=data.model_dump(mode="json"),
    )
    workflow.steps = [
        WorkflowStep(name="policy_verification", state=StepState.PENDING),
        WorkflowStep(name="claim_submission", state=StepState.PENDING),
    ]
    session.add(workflow)
    await session.flush()

    session.add(
        WorkflowIdempotencyKey(
            subject=subject,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            workflow_id=workflow.id,
        )
    )
    _audit(session, workflow.id, "workflow_created")

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await _find_existing(session, subject, key, fingerprint)
        if existing is None:
            raise
        return existing

    await _execute_workflow(session, workflow, data, authorization, key)
    await session.commit()
    await session.refresh(workflow)
    return workflow


async def get_workflow(session: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
    return await session.get(Workflow, workflow_id)


MAX_RETRY_COUNT = 3


async def retry_claim_workflow(
    session: AsyncSession,
    workflow_id: uuid.UUID,
    authorization: str | None,
) -> Workflow:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise KeyError("Workflow not found")

    if workflow.state == WorkflowState.COMPLETED:
        return workflow

    if workflow.state != WorkflowState.FAILED:
        raise WorkflowNotRetryable("Only failed workflows can be retried")

    if workflow.failure_category not in {
        "ClaimsServiceUnavailable",
        "PolicyServiceUnavailable",
    }:
        raise WorkflowNotRetryable("Workflow failure is not retryable")

    if workflow.retry_count >= MAX_RETRY_COUNT:
        raise WorkflowNotRetryable("Workflow retry limit exceeded")

    idempotency_result = await session.execute(
        select(WorkflowIdempotencyKey).where(
            WorkflowIdempotencyKey.workflow_id == workflow_id
        )
    )
    idempotency_record = idempotency_result.scalar_one_or_none()
    if idempotency_record is None or workflow.request_payload is None:
        raise WorkflowNotRetryable("Workflow cannot be safely retried")

    data = ClaimWorkflowCreate.model_validate(workflow.request_payload)
    workflow.retry_count += 1
    _audit(session, workflow.id, "retry_started", {"retry_count": workflow.retry_count})
    _workflow_state(session, workflow, WorkflowState.PENDING)
    workflow.failure_category = None

    for step in workflow.steps:
        _step_state(session, workflow, step, StepState.PENDING)
        step.started_at = None
        step.completed_at = None

    await _execute_workflow(
        session,
        workflow,
        data,
        authorization,
        idempotency_record.idempotency_key,
    )
    if workflow.state == WorkflowState.COMPLETED:
        _audit(session, workflow.id, "retry_succeeded", {"retry_count": workflow.retry_count})
    else:
        _audit(
            session,
            workflow.id,
            "retry_finished",
            {"retry_count": workflow.retry_count, "state": workflow.state.value},
        )
    await session.commit()
    await session.refresh(workflow)
    return workflow
