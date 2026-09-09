import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LegacyClaimIn(BaseModel):
    source_system: str = Field(min_length=1, max_length=100)
    legacy_claim_id: str = Field(min_length=1, max_length=255)
    policy_number: str | None = Field(default=None, max_length=255)
    policyholder_id: uuid.UUID | None = None
    claim_amount: Decimal = Field(ge=0, decimal_places=2)
    incident_date: date
    description: str = Field(min_length=1, max_length=10000)
    status: str = Field(default="submitted", min_length=1, max_length=50)
    raw_payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def incident_not_future(self) -> "LegacyClaimIn":
        if self.incident_date > date.today():
            raise ValueError("incident_date cannot be in the future")
        return self


class LegacyClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_system: str
    legacy_claim_id: str
    policy_number: str | None
    policyholder_id: uuid.UUID | None
    claim_amount: Decimal
    incident_date: date
    description: str
    status: str
    raw_payload: dict
    received_at: datetime
    updated_at: datetime
