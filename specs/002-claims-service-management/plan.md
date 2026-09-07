# Implementation Plan: Claims Service Management

**Branch**: `002-claims-service-management` | **Date**: 2026-09-07 | **Spec**: specs/002-claims-service-management/spec.md

**Input**: Feature specification from specs/002-claims-service-management/spec.md

## Summary

Build a Claims Service that manages the insurance claim lifecycle: file a new claim
against an existing policy, retrieve/list claims, and transition claim status through
a defined lifecycle (submitted -> under_review -> approved -> paid, or denied, or
closed). Every status transition writes an immutable audit record in the same database
transaction as the status change. Claim creation requires a live check against the
Policy Service to confirm the referenced policy exists and is in 'active' status,
using a synchronous HTTP call with a timeout and limited retry with backoff; if the
Policy Service remains unreachable after retries, claim creation is rejected with a
dependency-unavailable error. Access is role-scoped via JWT claims (agent, adjuster,
admin, customer) issued by the same Keycloak realm as the Policy Service. Technical
approach mirrors the Policy Service: a Python/FastAPI REST service backed by
PostgreSQL, using SQLAlchemy 2.0 async ORM and Alembic migrations, tested with pytest
and testcontainers, packaged as a Docker image for docker-compose-based local
development.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Alembic, asyncpg, python-jose (JWT validation), pydantic v2, httpx (outbound Policy Service calls with retry/backoff)

**Storage**: PostgreSQL 16 (separate schema/database from Policy Service - claims_db)

**Testing**: pytest, pytest-asyncio, httpx (async test client), testcontainers-python (real Postgres container for integration tests), respx or httpx mock transport for simulating Policy Service responses (success, not-active, not-found, unreachable/timeout) in tests without a live dependency

**Target Platform**: Linux container (Docker), runs locally via docker-compose alongside the Policy Service

**Performance Goals**: p95 claim retrieval under 500ms (per spec SC-004); the Policy Service verification call adds latency to claim creation only, bounded by timeout + retry budget (see Constraints)

**Constraints**: status update and audit record write MUST be atomic (single DB transaction, same pattern as Policy Service); claim creation MUST verify policy status via a live call to the Policy Service with a bounded total latency budget (2s connect/read timeout per attempt, up to 2 retries with exponential backoff, capped around 5s total) before failing with a dependency-unavailable error; no unauthenticated endpoints; audit records are append-only

**Scale/Scope**: single bounded-context service; about 7 REST endpoints (create, get, list, update-status, plus health/readiness); one Postgres schema owned exclusively by this service; one outbound HTTP dependency (Policy Service)

## Constitution Check

GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.

- Security-First (Principle I): PASS - all endpoints require a valid Keycloak-issued JWT (same realm/JWKS pattern as Policy Service, including the 10-minute cached JWKS lookup); role claims enforced per-endpoint via the existing require_roles dependency pattern, reused as a shared convention.
- Audit-First (Principle II): PASS - AuditRecord table is append-only; every status transition writes one audit row in the same transaction as the claim update, identical pattern to the Policy Service.
- Resilience (Principle III): PASS - this is the first feature to exercise this principle directly. The Policy Service dependency call uses an explicit timeout, bounded retry with backoff, and a clear failure mode (reject claim creation, no partial state) rather than hanging indefinitely or silently proceeding without verification.
- Contract-Driven Integration (Principle IV): PASS - Claims Service's own REST API is documented via FastAPI's OpenAPI schema, committed to contracts/claims-api.yaml. Additionally, Claims Service consumes the Policy Service's already-pinned contracts/policy-api.yaml (from the Policy Service feature) as the source of truth for the GET /policies/{id} response shape it depends on.
- Test-Verified Delivery (Principle V): PASS - every functional requirement (FR-001 through FR-008) and all four clarified edge cases map to at least one planned test in Phase 2 tasks, including simulated Policy Service failure modes.
- Polyglot by Design (Principle VI): PASS - Python service, owns its own Postgres schema exclusively (claims_db, separate from policy_db); does not reach into the Policy Service's database directly, only calls its public HTTP API.

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

specs/002-claims-service-management/ contains plan.md (this file), data-model.md (Phase 1 output), quickstart.md (Phase 1 output), contracts/claims-api.yaml (Phase 1 output, committed OpenAPI contract), and tasks.md (Phase 2 output from /speckit.tasks).

### Source Code (repository root)

Follows the same multi-service monorepo layout established by the Policy Service.

Layout for this feature:

services/claims/src/claims_service/main.py - FastAPI app entrypoint
services/claims/src/claims_service/api/routes.py - REST endpoints
services/claims/src/claims_service/models/claim.py - Claim ORM model
services/claims/src/claims_service/models/audit.py - AuditRecord ORM model
services/claims/src/claims_service/schemas/claim.py - Pydantic request/response schemas
services/claims/src/claims_service/services/claim_service.py - business logic, status transition rules
services/claims/src/claims_service/services/policy_client.py - httpx client for calling the Policy Service, with timeout/retry/backoff and typed error handling (PolicyNotFound, PolicyNotActive, PolicyServiceUnavailable)
services/claims/src/claims_service/auth/jwt.py - Keycloak JWT validation and role dependency (same implementation as Policy Service, duplicated per-service per Polyglot-by-Design; a shared auth library is a future refactor candidate, not in scope here)
services/claims/src/claims_service/db/session.py - async engine/session setup
services/claims/src/claims_service/db/migrations/ - Alembic migration scripts
services/claims/tests/unit/ - unit tests
services/claims/tests/integration/ - testcontainers-backed Postgres tests, with the Policy Service call mocked via httpx mock transport
services/claims/tests/contract/ - validates responses against contracts/claims-api.yaml
services/claims/Dockerfile
services/claims/pyproject.toml
services/claims/alembic.ini

**Structure Decision**: Follows the exact same internal layout as services/policy/
established in the Policy Service plan, with one addition: a services/policy_client.py
module encapsulating the outbound HTTP call to the Policy Service, since this is the
first service with a real synchronous dependency on another service in this platform.
This module is the natural seam for future resilience improvements (circuit breaker,
caching) if the platform grows.

## Complexity Tracking

No constitution violations - table not needed.
