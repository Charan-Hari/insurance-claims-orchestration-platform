# Claims Service

FastAPI service for filing, retrieving, and progressing insurance claims against
policies managed by the Policy Service. The local Docker Compose stack runs
PostgreSQL, Keycloak, Policy Service, and this service together.

## Run Locally

From the repository root, with the shared `.env` already configured for the
Policy Service:

```sh
docker compose up --build
```

The services are available at:

- Claims Service: `http://localhost:8001`
- Policy Service: `http://localhost:8000`
- Keycloak: `http://localhost:8080`
- PostgreSQL: internal to the Compose network as `postgres:5432`

The claims container waits for PostgreSQL, Keycloak, and Policy Service health
checks, runs `alembic upgrade head`, and then starts Uvicorn. Stop the stack
with `docker compose down`; add `-v` only when you want to delete the
persisted PostgreSQL volume.

Claims Service depends on Policy Service being healthy and reachable, because
filing a claim requires a live call to `GET /policies/{policy_id}` on the
Policy Service to confirm the policy is currently `active`.

## Configure Keycloak

Claims Service reuses the same Keycloak realm and roles as Policy Service
(`agent`, `underwriter`, `admin`, `customer` — note Claims Service additionally
recognizes `adjuster` for status updates; add an `adjuster` realm role and
assign it to a test user if you want to exercise claim status transitions).

Customer access uses the Keycloak JWT `sub` claim as the policyholder ID, so a
customer-owned claim must reference a policy whose `policyholder_id` matches
that UUID.

## Get A Test JWT

```sh
TOKEN=$(curl -s -X POST \
  "http://localhost:8080/realms/${KEYCLOAK_REALM:-policy}/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=policy-service' \
  -d 'username=agent@example.com' \
  -d 'password=CHANGE_ME' \
  -d 'grant_type=password' | jq -r .access_token)
```

Replace the username and password with a test user configured in Keycloak.
The token must contain the role required by the endpoint.

## API Examples

These examples assume `TOKEN` contains a valid agent, adjuster, or admin
token, and `POLICY_ID` is a real, currently `active` policy created via the
Policy Service. UUIDs are examples; use real values in your requests.

File a claim against an active policy:

```sh
curl -X POST http://localhost:8001/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy_id": "POLICY_ID",
    "claim_amount": "15000.00",
    "incident_date": "2026-08-15",
    "description": "Water damage from burst pipe in kitchen."
  }'
```

Retrieve a claim by ID:

```sh
curl http://localhost:8001/claims/CLAIM_ID \
  -H "Authorization: Bearer $TOKEN"
```

List claims for a policyholder:

```sh
curl http://localhost:8001/policyholders/POLICYHOLDER_ID/claims \
  -H "Authorization: Bearer $TOKEN"
```

Update a claim status with an adjuster or admin token:

```sh
curl -X PATCH http://localhost:8001/claims/CLAIM_ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status": "under_review"}'
```

Valid status transitions are enforced by the service
(`submitted -> under_review -> approved -> paid`,
`under_review -> denied`, `under_review -> closed`). Every accepted
transition creates an audit record in the same database transaction as the
claim status update; rejected transitions leave the claim unchanged and write
no audit record.

## Tests

From the repository root, with Docker available for the integration tests:

```sh
cd services/claims
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/claims_db pytest -q
```

Run the test layers independently when diagnosing a failure:

```sh
pytest -q tests/unit
pytest -q tests/contract
pytest -q tests/integration
```

Integration tests mock the Policy Service boundary (`policy_client.get_policy`)
so they run without a live Policy Service. To verify the real cross-service
call, use the `docker compose up` stack and the curl examples above against a
policy actually created through the running Policy Service.

## Environment Variables

| Variable | Used by | Local example | Description |
| --- | --- | --- | --- |
| `POSTGRES_USER` | Compose/PostgreSQL | `policy_user` | Shared PostgreSQL username. |
| `POSTGRES_PASSWORD` | Compose/PostgreSQL | `policy_dev_password` | Local-only PostgreSQL password. |
| `CLAIMS_POSTGRES_DB` | Compose/PostgreSQL | `claims_db` | Claims database name (separate from Policy's `policy_db`). |
| `KEYCLOAK_REALM` | Compose/Claims Service | `policy` | Keycloak realm used by the service (shared with Policy Service). |
| `KEYCLOAK_AUDIENCE` | Compose/Claims Service | `policy-service` | JWT audience and local client ID (shared with Policy Service). |
| `DATABASE_URL` | Claims Service/tests | `postgresql+asyncpg://...` | Async PostgreSQL connection URL, pointed at the `claims_db` database. |
| `KEYCLOAK_ISSUER` | Claims Service | `http://keycloak:8080/realms/policy` | Keycloak issuer URL used for JWT validation. |
| `POLICY_SERVICE_BASE_URL` | Claims Service | `http://policy-service:8000` | Base URL used by `policy_client.py` to verify policy status. Never point this at an untrusted host. |

Copy `.env.example` to `.env` for the Compose defaults. Never use these
values outside local development, and never commit `.env` or production
secrets.

## Troubleshooting

**Claims Service is not starting:** Check `docker compose logs claims-service`.
The container waits for PostgreSQL, Keycloak, and Policy Service, runs
`alembic upgrade head`, and only then starts Uvicorn. If Policy Service is not
healthy yet, Claims Service will not start.

**`POST /claims` returns `503`:** The Policy Service could not be reached
within the retry/backoff budget (2s timeout, 2 retries). Check
`docker compose logs policy-service` and confirm it is healthy and reachable
at `POLICY_SERVICE_BASE_URL`.

**`POST /claims` returns `400`:** Either the referenced policy does not exist,
or it exists but is not currently `active`. Confirm the policy's status via
`GET /policies/{policy_id}` on the Policy Service.

**JWT requests return `401`:** Verify `KEYCLOAK_ISSUER` matches the realm URL,
`KEYCLOAK_AUDIENCE` matches the client ID, and that the token contains a
matching `kid`, issuer, audience, and realm role.

**Requests return `403`:** Confirm the user has the required realm role.
Agents and adjusters can file claims, adjusters and admins can update claim
status, and customers can only access their own claims.

**`GET`/list requests return `404` for a claim you expect to see:** Claims
Service intentionally returns `404` (not `403`) when a customer requests a
claim or policyholder claim list they do not own, to avoid leaking the
existence of another policyholder's claims.

## Idempotent Claim Creation

`POST /claims` requires an `Idempotency-Key` request header.

For the same authenticated subject:

- Reusing the same key with the same request returns the original claim.
- Reusing the same key with a different request returns `409 Conflict`.
- Missing or blank keys return `400`.
- Idempotency keys are persisted atomically with claim creation.
- Authorization tokens are never stored or logged.

Example headers:

- `Authorization: Bearer $TOKEN`
- `Idempotency-Key: claim-request-001`
- `Content-Type: application/json`

The idempotency key is scoped to the authenticated subject, so different users
may safely use the same key value.
