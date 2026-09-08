# Orchestrator Implementation Plan

## Architecture

Create `services/orchestrator` as an independently deployable Python 3.12
FastAPI service.

The service owns:

- Workflow records
- Workflow step records
- Idempotency keys
- Workflow audit events
- Retry and reconciliation state

The service communicates with Policy Service and Claims Service only over HTTP.

## Technology

- Python 3.12
- FastAPI
- SQLAlchemy 2.0 async
- asyncpg
- Alembic
- httpx
- PostgreSQL
- Pytest
- Testcontainers PostgreSQL

## API

- `POST /workflows/claims`
- `GET /workflows/{workflow_id}`
- `POST /workflows/{workflow_id}/retry`
- `GET /health`
- `GET /readiness`

## Persistence

Use separate tables for:

- `workflows`
- `workflow_steps`
- `workflow_audit_events`
- `idempotency_keys`

Workflow creation and idempotency registration must be atomic. Unique database
constraints must protect against concurrent duplicate requests.

## Resilience

Each downstream client must use:

- Bounded connect/read timeout
- At most two retries
- Exponential backoff
- Typed exceptions
- Structured outcome logging
- No Authorization-header logging

Retry only transport failures and HTTP 5xx responses. Do not retry business
responses such as `400`, `401`, `403`, or `404`.

## Authorization

Reuse the existing JWT validation pattern. Customers may access only workflows
whose policyholder ID matches their JWT subject. Agent, adjuster, and admin roles
may operate workflows according to the endpoint policy.

## Compensation

Because Policy Service and Claims Service do not expose destructive rollback
operations, compensation is non-destructive:

- Prevent claim creation when policy verification fails.
- Retry claim creation with the same idempotency key after an ambiguous response.
- Mark unreconciled outcomes as `reconciliation_required`.
- Persist an operational audit event for every compensation decision.

## Testing

Write tests before implementation:

- State-machine unit tests
- Idempotency concurrency tests
- HTTP client retry tests
- OpenAPI contract tests
- Real-Postgres integration tests
- Policy and Claims boundary tests
- Failure and reconciliation tests
