import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from policy_service.models.policy import PolicyStatus


class PolicyCreate(BaseModel):
    policyholder_id: uuid.UUID
    coverage_type: str = Field(min_length=1, max_length=100)
    coverage_limits: dict[str, Any]
    effective_date: date
    expiry_date: date
    premium_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)

    @model_validator(mode="after")
    def validate_dates(self) -> "PolicyCreate":
        if self.expiry_date <= self.effective_date:
            raise ValueError("expiry_date must be after effective_date")
        return self


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policyholder_id: uuid.UUID
    coverage_type: str
    coverage_limits: dict[str, Any]
    effective_date: date
    expiry_date: date
    status: PolicyStatus
    premium_amount: Decimal | None
    created_at: datetime
    updated_at: datetime


class PolicyStatusUpdate(BaseModel):
    status: PolicyStatus


class AuditRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    actor_id: str
    old_status: PolicyStatus
    new_status: PolicyStatus
    created_at: datetime