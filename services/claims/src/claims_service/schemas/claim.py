import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from claims_service.models.claim import ClaimStatus


class ClaimCreate(BaseModel):
    policy_id: uuid.UUID
    policyholder_id: uuid.UUID
    claim_amount: Decimal = Field(ge=0, decimal_places=2)
    incident_date: date
    description: str = Field(min_length=1)
    adjuster_notes: str | None = None

    @model_validator(mode="after")
    def validate_incident_date(self) -> "ClaimCreate":
        if self.incident_date > date.today():
            raise ValueError("incident_date cannot be in the future")
        return self


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    policyholder_id: uuid.UUID
    claim_amount: Decimal
    incident_date: date
    description: str
    adjuster_notes: str | None
    status: ClaimStatus
    created_at: datetime
    updated_at: datetime


class ClaimStatusUpdate(BaseModel):
    status: ClaimStatus


class AuditRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    actor_id: str
    old_status: ClaimStatus
    new_status: ClaimStatus
    created_at: datetime