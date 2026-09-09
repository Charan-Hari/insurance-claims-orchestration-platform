# Platform Eventing

This isolated service provides a PostgreSQL transactional outbox. Producers construct an
`EventEnvelope` and append it in the same database transaction as their business write
(the repository accepts an existing `AsyncSession`). `(producer, idempotency_key)` is
unique, so retries return the original event instead of creating duplicates.

`services/eventing/sql/001_event_outbox.sql` is the deployable schema. The API also
creates the table on startup for a frictionless local Compose run; production
deployments should apply the SQL through the normal migration pipeline.

## API

`POST /events` accepts the envelope and returns `event_id`, `accepted`, and `status`.
`/health` is liveness; `/readiness` checks PostgreSQL. Example event helpers are
`claim_created` and `workflow_transitioned`.

`OutboxWorker` claims rows with PostgreSQL `FOR UPDATE SKIP LOCKED`, publishes through
an injected `Publisher`, and applies bounded exponential retry with durable error state.
It intentionally does not choose a broker; a Kafka, HTTP, or queue adapter can implement
the two-method `publish` protocol.

## Follow-up integration points

Existing claims, policy, orchestrator, payments, and legacy services are unchanged.
Each service should next share its business transaction/session with `EventRepository.append`
and run a worker adapter appropriate to its deployment. Delivery is at-least-once; consumers
must deduplicate by `event_id`.

Run tests with `pip install -e '.[dev]'` then `pytest`.
