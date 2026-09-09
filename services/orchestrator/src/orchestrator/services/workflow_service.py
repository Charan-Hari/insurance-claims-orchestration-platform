import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models import Workflow, WorkflowIdempotencyKey, WorkflowStep
from orchestrator.schemas.workflow import (
    ClaimWorkflowCreate,
    StepState,
    WorkflowState,
)
from orchestrator.services import claims_client, policy_client
from orchestrator.services.claims_client import ClaimsServiceRejected, ClaimsServiceUnavailable
from orchestrator.services.policy_client import PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable


class WorkflowConflict(ValueError):
    pass


class WorkflowNotRetryable(ValueError):
    pass


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

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await _find_existing(session, subject, key, fingerprint)
        if existing is None:
            raise
        return existing

    try:
        await policy_client.get_policy(data.policy_id, authorization)

        claim = await claims_client.create_claim(
            policy_id=data.policy_id,
            policyholder_id=data.policyholder_id,
            claim_amount=data.claim_amount,
            incident_date=data.incident_date,
            description=data.description,
            adjuster_notes=data.adjuster_notes,
            authorization=authorization,
            idempotency_key=key,
        )

        workflow.claim_id = uuid.UUID(claim["id"])
        workflow.state = WorkflowState.COMPLETED
        workflow.steps[0].state = StepState.SUCCEEDED
        workflow.steps[1].state = StepState.SUCCEEDED
        now = datetime.now(timezone.utc)
        workflow.steps[0].completed_at = now
        workflow.steps[1].completed_at = now
    except (ClaimsServiceRejected, ClaimsServiceUnavailable, PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable) as exc:
        workflow.state = WorkflowState.FAILED
        workflow.failure_category = type(exc).__name__
        for step in workflow.steps:
            if step.state in {StepState.PENDING, StepState.RUNNING}:
                step.state = StepState.FAILED
                step.error_category = type(exc).__name__

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
    workflow.state = WorkflowState.PENDING
    workflow.failure_category = None

    for step in workflow.steps:
        step.state = StepState.PENDING
        step.error_category = None
        step.started_at = None
        step.completed_at = None

    try:
        await policy_client.get_policy(data.policy_id, authorization)
        claim = await claims_client.create_claim(
            policy_id=data.policy_id,
            policyholder_id=data.policyholder_id,
            claim_amount=data.claim_amount,
            incident_date=data.incident_date,
            description=data.description,
            adjuster_notes=data.adjuster_notes,
            authorization=authorization,
            idempotency_key=idempotency_record.idempotency_key,
        )
        workflow.claim_id = uuid.UUID(claim["id"])
        workflow.state = WorkflowState.COMPLETED
        for step in workflow.steps:
            step.state = StepState.SUCCEEDED
            step.completed_at = datetime.now(timezone.utc)
    except (ClaimsServiceRejected, ClaimsServiceUnavailable, PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable) as exc:
        workflow.state = WorkflowState.FAILED
        workflow.failure_category = type(exc).__name__
        for step in workflow.steps:
            step.state = StepState.FAILED
            step.error_category = type(exc).__name__

    await session.commit()
    await session.refresh(workflow)
    return workflow
