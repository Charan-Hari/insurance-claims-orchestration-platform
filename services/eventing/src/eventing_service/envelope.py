from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    """Stable, self-contained contract stored in the outbox payload."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=1, max_length=200)
    aggregate_type: str = Field(min_length=1, max_length=100)
    aggregate_id: str = Field(min_length=1, max_length=200)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    producer: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=255)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def claim_created(*, claim_id: str, idempotency_key: str, producer: str = "claims-service", **payload: Any) -> EventEnvelope:
    return EventEnvelope(
        event_type="claim.created",
        aggregate_type="claim",
        aggregate_id=claim_id,
        producer=producer,
        idempotency_key=idempotency_key,
        payload={"claim_id": claim_id, **payload},
    )


def workflow_transitioned(
    *, workflow_id: str, from_state: str, to_state: str, idempotency_key: str,
    producer: str = "orchestrator-service", **payload: Any,
) -> EventEnvelope:
    return EventEnvelope(
        event_type="workflow.transitioned",
        aggregate_type="workflow",
        aggregate_id=workflow_id,
        producer=producer,
        idempotency_key=idempotency_key,
        payload={"workflow_id": workflow_id, "from_state": from_state, "to_state": to_state, **payload},
    )
