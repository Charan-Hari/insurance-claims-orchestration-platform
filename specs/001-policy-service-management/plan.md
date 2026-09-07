# Implementation Plan: Policy Service Management

**Branch**: `001-policy-service-management` | **Date**: 2026-09-06 | **Spec**: specs/001-policy-service-management/spec.md

**Input**: Feature specification from specs/001-policy-service-management/spec.md

## Summary

Build a Policy Service that manages the insurance policy lifecycle for a property and
casualty carrier: create policy applications, retrieve/list policies, and transition
policy status through a defined lifecycle (draft -> pending_underwriting -> active ->
cancelled -> expired -> renewed -> pending_underwriting). Every status transition writes
an immutable audit record in the same database transaction as the status change. Access
is role-scoped via JWT claims (agent, underwriter, admin, customer) issued by Keycloak.
Technical approach: a Python/FastAPI REST service backed by PostgreSQL, using SQLAlchemy
2.0 async ORM and Alembic migrations, tested with pytest and testcontainers, packaged as
a Docker image for docker-compose-based local development.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Alembic, asyncpg, python-jose (JWT validation), pydantic v2

**Storage**: PostgreSQL 16

**Testing**: pytest, pytest-asyncio, httpx (async test client), testcontainers-python (real Postgres in a container for integration tests)

**Target Platform**: Linux container (Docker), runs locally via docker-compose

**Project Type**: web-service (backend REST API, part of a larger multi-service monorepo)

**Performance Goals**: p95 policy retrieval under 500ms (per spec SC-003)

**Constraints**: status update and audit record write MUST be atomic (single DB transaction, per spec Clarifications); no unauthenticated endpoints (constitution Principle I); audit records are append-only, never updated or deleted (constitution Principle II)

**Scale/Scope**: single bounded-context service; about 7 REST endpoints (create, get, list, update-status, plus health/readiness); one Postgres schema owned exclusively by this service (constitution Principle VI, no other service may access this database directly)

## Constitution Check

GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.

- Security-First (Principle I): PASS - all endpoints require a valid Keycloak-issued JWT; role claims enforced per-endpoint via a FastAPI dependency; no secrets hardcoded, DB credentials and JWT issuer/audience come from environment variables.
- Audit-First (Principle II): PASS - AuditRecord table is append-only (no UPDATE/DELETE exposed via the ORM layer for this table); every status transition writes one audit row in the same transaction as the policy update.
- Resilience (Principle III): N/A for this feature - Policy Service has no outbound saga/compensation responsibilities itself; it is a participant called by the future Orchestrator, which owns compensation logic.
- Contract-Driven Integration (Principle IV): PASS - REST API documented via FastAPI's auto-generated OpenAPI schema, checked into contracts/policy-api.yaml as a committed artifact so other services/contract tests can pin against a specific version.
- Test-Verified Delivery (Principle V): PASS - every functional requirement (FR-001 through FR-007) and both clarified edge cases map to at least one planned test in Phase 2 tasks.
- Polyglot by Design (Principle VI): PASS - Python service, owns its own Postgres schema exclusively.

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

specs/001-policy-service-management/ contains plan.md (this file), research.md (Phase 0 output), data-model.md (Phase 1 output), quickstart.md (Phase 1 output), contracts/policy-api.yaml (Phase 1 output, committed OpenAPI contract), and tasks.md (Phase 2 output from /speckit.tasks).

### Source Code (repository root)

This repository hosts multiple independently-deployable services (Policy, Claims, Orchestrator, Legacy Adapter, Payments, Copilot) plus a shared Angular frontend, so the monorepo uses a services/ plus frontend/ structure rather than a single-project layout.

Layout for this feature:

services/policy/src/policy_service/main.py - FastAPI app entrypoint
services/policy/src/policy_service/api/routes.py - REST endpoints
services/policy/src/policy_service/models/policy.py - Policy ORM model
services/policy/src/policy_service/models/audit.py - AuditRecord ORM model
services/policy/src/policy_service/schemas/policy.py - Pydantic request/response schemas
services/policy/src/policy_service/services/policy_service.py - business logic, status transition rules
services/policy/src/policy_service/auth/jwt.py - Keycloak JWT validation and role dependency
services/policy/src/policy_service/db/session.py - async engine/session setup
services/policy/src/policy_service/db/migrations/ - Alembic migration scripts
services/policy/tests/unit/ - unit tests
services/policy/tests/integration/ - testcontainers-backed Postgres tests
services/policy/tests/contract/ - validates responses against contracts/policy-api.yaml
services/policy/Dockerfile
services/policy/pyproject.toml
services/policy/alembic.ini

**Structure Decision**: Multi-service monorepo. This feature lives entirely under
services/policy/. Future features (Claims, Orchestrator, etc.) will each get their own
top-level directory under services/, following the same internal layout
(src/<service_name>/{api,models,schemas,services,auth,db}, tests/{unit,integration,
contract}). This keeps each service independently buildable/testable/deployable while
sharing one repository, one CI pipeline, and one Spec-Kit delivery process.

## Complexity Tracking

No constitution violations - table not needed.
