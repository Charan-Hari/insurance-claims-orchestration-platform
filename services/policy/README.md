# Policy Service

FastAPI service for creating, retrieving, and progressing insurance policies. The local Docker Compose stack runs PostgreSQL, Keycloak, and this service together.

## Run Locally

Copy the dev-safe environment template and start the stack:

```sh
cp .env.example .env
docker compose up --build
```

The services are available at:

- Policy Service: `http://localhost:8000`
- Keycloak: `http://localhost:8080`
- PostgreSQL: internal to the Compose network as `postgres:5432`

The policy container waits for PostgreSQL and Keycloak health checks, runs `alembic upgrade head`, and then starts Uvicorn. Stop the stack with `docker compose down`; add `-v` only when you want to delete the persisted PostgreSQL volume.

## Configure Keycloak

1. Open `http://localhost:8080` and sign in to the administration console with `KEYCLOAK_ADMIN_USERNAME` and `KEYCLOAK_ADMIN_PASSWORD` from `.env`.
2. Create a realm named `policy` or use the realm named by `KEYCLOAK_REALM`.
3. Create a client named `policy-service` or use the value of `KEYCLOAK_AUDIENCE`. Set **Client authentication** off and enable **Direct access grants** for local testing.
4. In the realm, create these realm roles: `agent`, `underwriter`, `admin`, and `customer`.
5. Create a test user, set a non-temporary password, and assign one of those realm roles. For the examples below, assign `agent` to the user.

For a customer token, assign the `customer` role. Customer access uses the Keycloak JWT `sub` claim as the policyholder ID, so a customer-owned policy must use that UUID as `policyholder_id`.

## Get A Test JWT

With a user configured for direct access grants, request a token from the realm token endpoint:

```sh
TOKEN=$(curl -s -X POST \
  "http://localhost:8080/realms/${KEYCLOAK_REALM:-policy}/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=policy-service' \
  -d 'username=agent@example.com' \
  -d 'password=change-me-in-keycloak' \
  -d 'grant_type=password' | jq -r .access_token)
```

Replace the username and password with the test user created in Keycloak. The token must contain the role required by the endpoint. Decode the JWT payload locally, without sending it to a third-party service, to inspect the `sub` claim when testing customer ownership.

## API Examples

These examples assume `TOKEN` contains a valid agent, underwriter, or admin token. UUIDs are examples; use real values in your requests.

Create a policy application:

```sh
curl -X POST http://localhost:8000/policies \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "policyholder_id": "11111111-1111-1111-1111-111111111111",
    "coverage_type": "property",
    "coverage_limits": {"dwelling": 250000, "liability": 500000},
    "effective_date": "2026-10-01",
    "expiry_date": "2027-10-01",
    "premium_amount": "1200.00"
  }'
```

Retrieve a policy by ID:

```sh
curl http://localhost:8000/policies/POLICY_ID \
  -H "Authorization: Bearer $TOKEN"
```

List policies for a policyholder:

```sh
curl http://localhost:8000/policyholders/11111111-1111-1111-1111-111111111111/policies \
  -H "Authorization: Bearer $TOKEN"
```

Update a policy status with an underwriter or admin token:

```sh
curl -X PATCH http://localhost:8000/policies/POLICY_ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status": "pending_underwriting"}'
```

Valid status transitions are enforced by the service. Every accepted transition creates an audit record in the same database transaction as the policy update.

## Tests

From the repository root, with Docker available for the integration tests, run the complete suite:

```sh
cd services/policy
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db pytest -q
```

Run the test layers independently when diagnosing a failure:

```sh
pytest -q tests/unit
pytest -q tests/contract
pytest -q tests/integration
```

## Environment Variables

| Variable | Used by | Local example | Description |
| --- | --- | --- | --- |
| `POSTGRES_USER` | Compose/PostgreSQL | `policy_user` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | Compose/PostgreSQL | `policy_dev_password` | Local-only PostgreSQL password. |
| `POSTGRES_DB` | Compose/PostgreSQL | `policy_db` | Policy database name. |
| `KEYCLOAK_ADMIN_USERNAME` | Compose/Keycloak | `admin` | Local Keycloak bootstrap administrator. |
| `KEYCLOAK_ADMIN_PASSWORD` | Compose/Keycloak | `keycloak_dev_password` | Local-only Keycloak administrator password. |
| `KEYCLOAK_REALM` | Compose/Policy Service | `policy` | Keycloak realm used by the service. |
| `KEYCLOAK_AUDIENCE` | Compose/Policy Service | `policy-service` | JWT audience and local client ID. |
| `DATABASE_URL` | Policy Service/tests | `postgresql+asyncpg://...` | Async PostgreSQL connection URL. Compose builds this from the PostgreSQL variables. |
| `KEYCLOAK_ISSUER` | Policy Service | `http://keycloak:8080/realms/policy` | Keycloak issuer URL used for JWT validation. |

Copy `.env.example` to `.env` for the Compose defaults. Never use these values outside local development, and never commit `.env` or production secrets.

## Troubleshooting

**Keycloak is not healthy:** Check `docker compose logs keycloak`. Confirm the container has finished its first startup and that port 8080 is free. The readiness probe uses Keycloak's management endpoint on port 9000 and requires `KC_HEALTH_ENABLED=true`.

**Policy Service is not starting:** Check `docker compose logs policy-service`. The container waits for PostgreSQL and Keycloak, runs `alembic upgrade head`, and only then starts Uvicorn. A migration error usually means the database volume contains an incomplete or incompatible schema; for disposable local data, run `docker compose down -v` and start again.

**JWT requests return 401:** Verify `KEYCLOAK_ISSUER` matches the realm URL, `KEYCLOAK_AUDIENCE` matches the client ID, and that the token contains a matching `kid`, issuer, audience, and realm role.

**Requests return 403:** Confirm the user has the required realm role. Agents and underwriters can create policies, underwriters and admins can update status, and customers can only access their own policyholder ID.
