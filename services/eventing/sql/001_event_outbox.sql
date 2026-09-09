CREATE TABLE IF NOT EXISTS event_outbox (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(200) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_until TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_event_outbox_idempotency UNIQUE (producer, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_event_outbox_delivery ON event_outbox(status, available_at);
CREATE INDEX IF NOT EXISTS ix_event_outbox_aggregate ON event_outbox(aggregate_type, aggregate_id);
