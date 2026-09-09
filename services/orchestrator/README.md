# Orchestrator Service

Coordinates claim workflows across Policy and Claims Services.

## Endpoints

- `POST /workflows/claims` - starts an idempotent claim workflow.
- `GET /workflows/{workflow_id}` - retrieves workflow status.
- `POST /workflows/{workflow_id}/retry` - retries eligible failed workflows.

## Local validation

```bash
PYTHONPATH=src pytest -q tests
```

The service requires PostgreSQL, Keycloak, Policy Service, and Claims Service.
Docker Compose exposes it on port `8002`.
