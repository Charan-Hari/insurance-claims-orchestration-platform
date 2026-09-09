import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WorkflowState(str, enum.Enum):
    PENDING = "pending"
    POLICY_VERIFIED = "policy_verified"
    CLAIM_SUBMITTED = "claim_submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class StepState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ClaimWorkflowCreate(BaseModel):
    policy_id: uuid.UUID
    policyholder_id: uuid.UUID
    claim_amount: Decimal = Field(ge=0, decimal_places=2)
    incident_date: date
    description: str = Field(min_length=1)
    adjuster_notes: str | None = None


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    state: StepState
    error_category: str | None
    started_at: datetime | None
    completed_at: datetime | None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    policyholder_id: uuid.UUID
    state: WorkflowState
    claim_id: uuid.UUID | None
    failure_category: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepRead] = []
