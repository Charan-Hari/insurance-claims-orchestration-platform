# Orchestrator Service

Coordinates claim workflows across Policy and Claims Services.

## Endpoints

- `POST /workflows/claims` - starts an idempotent claim workflow.
- `GET /workflows/{workflow_id}` - retrieves workflow status.
- `POST /workflows/{workflow_id}/retry` - retries eligible failed workflows.

Workflow and step transitions are written to the append-only
`workflow_audit_event` table in the same transaction as the workflow update.
Downstream claim POSTs use the original idempotency key for bounded retries. If
the final response is ambiguous or cannot be reconciled, the workflow is marked
`reconciliation_required` and an operational `reconciliation_required` audit
event is recorded; no Policy or Claims data is deleted or modified.

## Local validation

```bash
PYTHONPATH=src pytest -q tests
```

The service requires PostgreSQL, Keycloak, Policy Service, and Claims Service.
Docker Compose exposes it on port `8002`.
