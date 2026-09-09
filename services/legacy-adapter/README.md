# Legacy Adapter Service

FastAPI adapter for importing claims from legacy systems. `POST /legacy/claims`
requires a Keycloak bearer token and persists each `(source_system,
legacy_claim_id)` exactly once. Replaying an identical record returns `200`
with the original record; reusing the identifier with different content returns
`409`.

## Run locally

```sh
pip install -e ".[dev]"
$env:DATABASE_URL="postgresql+asyncpg://user:password@localhost/legacy_db"
alembic upgrade head
uvicorn legacy_adapter.main:app --reload
```

`/health` is a liveness check and `/readiness` verifies PostgreSQL connectivity.
Every response includes `X-Request-ID` (or propagates the caller's valid
request ID). Configure `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, and optionally
`LEGACY_ADAPTER_ROLES` (default: `agent,admin,legacy-adapter`).

Example payload:

```json
{"source_system":"mainframe","legacy_claim_id":"CLM-1001",
 "policy_number":"POL-44","claim_amount":"1250.00",
 "incident_date":"2026-01-15","description":"Water damage",
 "status":"submitted","raw_payload":{"batch":"2026-01-15"}}
```
