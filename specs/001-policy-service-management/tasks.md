# Tasks: Policy Service Management

**Input**: Design documents from specs/001-policy-service-management/
**Prerequisites**: plan.md, spec.md

**Tests**: Tests are included for every functional requirement per constitution
Principle V (Test-Verified Delivery). Test tasks are written before their
corresponding implementation tasks.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested, and demoed independently. [P] marks a task that can run
in parallel with other [P] tasks in the same phase (different files, no
shared dependency).

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create services/policy/ directory skeleton (src/policy_service/{api,models,schemas,services,auth,db}, tests/{unit,integration,contract}) per plan.md Project Structure
- [x] T002 Create services/policy/pyproject.toml with dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, python-jose[cryptography], pydantic, pytest, pytest-asyncio, httpx, testcontainers
- [x] T003 [P] Create services/policy/Dockerfile (python:3.12-slim base, install deps, run uvicorn)
- [x] T004 [P] Create services/policy/alembic.ini and services/policy/src/policy_service/db/migrations/ scaffold (alembic init)
- [x] T005 [P] Create services/policy/src/policy_service/db/session.py with async SQLAlchemy engine/session factory reading DATABASE_URL from environment
- [x] T006 [P] Create services/policy/src/policy_service/auth/jwt.py: JWT validation against Keycloak issuer/JWKS, decode role claim, raise 401/403 as appropriate
- [x] T007 Create services/policy/src/policy_service/main.py: FastAPI app instance, health/readiness endpoints, router registration

**Checkpoint**: Service skeleton runs (`uvicorn` boots), health check returns 200. No business logic yet.

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T008 Create services/policy/src/policy_service/models/policy.py: Policy ORM model (id, policyholder_id, coverage_type, coverage_limits, effective_date, expiry_date, status, premium_amount, created_at, updated_at)
- [x] T009 Create services/policy/src/policy_service/models/audit.py: AuditRecord ORM model (id, policy_id FK, actor_id, old_status, new_status, created_at) - no update/delete methods exposed
- [x] T010 Generate initial Alembic migration for policy and audit_record tables in services/policy/src/policy_service/db/migrations/versions/
- [x] T011 Create services/policy/src/policy_service/schemas/policy.py: Pydantic schemas (PolicyCreate, PolicyRead, PolicyStatusUpdate, AuditRecordRead)
- [x] T012 Define the status transition state machine (valid transitions map per spec Clarifications) in services/policy/src/policy_service/services/policy_service.py

**Checkpoint**: DB schema exists, migrations apply cleanly against a local Postgres container. No endpoints wired yet.

## Phase 3: User Story 1 - Create Policy Application (Priority: P1)

**Goal**: Agent/underwriter can create a policy application, persisted in 'draft' status. Customers are denied.

**Independent Test**: POST a valid policy payload as an agent -> 201 with status=draft. POST as a customer -> 403.

- [x] T013 [P] [US1] Unit test: services/policy/tests/unit/test_policy_service_create.py - validates draft status default, rejects missing required fields
- [x] T014 [P] [US1] Contract test: services/policy/tests/contract/test_create_policy_contract.py - validates request/response shape against contracts/policy-api.yaml
- [x] T015 [US1] Integration test: services/policy/tests/integration/test_create_policy.py - agent creates policy (201, draft), customer attempt denied (403), using testcontainers Postgres
- [x] T016 [US1] Implement create_policy business logic in services/policy/src/policy_service/services/policy_service.py
- [x] T017 [US1] Implement POST /policies endpoint in services/policy/src/policy_service/api/routes.py with role dependency (agent, underwriter only)
- [x] T018 [US1] Run tests T013-T015, confirm green

**Checkpoint**: User Story 1 fully working and independently testable/demoable.

## Phase 4: User Story 2 - Retrieve Policy (Priority: P1)

**Goal**: Customers view only their own policy; admins view any policy; listing by policyholder works.

**Independent Test**: Customer GETs own policy -> 200. Customer GETs another's policy -> 403. Admin GETs any policy -> 200.

- [x] T019 [P] [US2] Unit test: services/policy/tests/unit/test_policy_service_get.py - ownership check logic
- [x] T020 [P] [US2] Contract test: services/policy/tests/contract/test_get_policy_contract.py
- [x] T021 [US2] Integration test: services/policy/tests/integration/test_get_policy.py - own/other/admin access scenarios (per spec Acceptance Scenarios 2.1-2.3)
- [x] T022 [US2] Implement get_policy_by_id and list_policies_for_policyholder in services/policy/src/policy_service/services/policy_service.py with ownership/role enforcement
- [x] T023 [US2] Implement GET /policies/{id} and GET /policyholders/{id}/policies endpoints in services/policy/src/policy_service/api/routes.py
- [x] T024 [US2] Run tests T019-T021, confirm green

**Checkpoint**: User Stories 1 and 2 both working independently. Retrieval performance (SC-003, p95 < 500ms) spot-checked.

## Phase 5: User Story 3 - Update Policy Status (Priority: P2)

**Goal**: Underwriter transitions policy status; every transition writes an immutable audit record atomically; invalid transitions rejected; customers denied.

**Independent Test**: Underwriter transitions draft -> pending_underwriting -> 200 + audit row created. Invalid transition (active -> draft) -> 400, no audit row, no status change. Customer attempt -> 403.

- [x] T025 [P] [US3] Unit test: services/policy/tests/unit/test_status_transitions.py - valid/invalid transition matrix per spec Clarifications
- [x] T026 [P] [US3] Contract test: services/policy/tests/contract/test_update_status_contract.py
- [x] T027 [US3] Integration test: services/policy/tests/integration/test_update_policy_status.py - valid transition + audit row atomicity, invalid transition rejected with no partial state, customer denied (per spec Acceptance Scenarios 3.1-3.2 and Edge Cases)
- [x] T028 [US3] Implement update_policy_status in services/policy/src/policy_service/services/policy_service.py: single DB transaction wrapping status update + audit insert, rollback both on any failure
- [x] T029 [US3] Implement PATCH /policies/{id}/status endpoint in services/policy/src/policy_service/api/routes.py with role dependency (underwriter, admin only)
- [x] T030 [US3] Run tests T025-T027, confirm green, explicitly verify no audit row exists after a rejected invalid transition

**Checkpoint**: All three user stories complete and independently testable. Full FR-001 through FR-007 coverage achieved.

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T031 [P] Export OpenAPI schema from running service to contracts/policy-api.yaml, commit as the pinned contract artifact
- [x] T032 [P] Add structured logging (request id, actor id, action) to all endpoints per constitution audit/observability requirements
- [x] T033 [P] Write services/policy/README.md: local run instructions (docker-compose), environment variables required, how to run tests
- [x] T034 Add services/policy to root docker-compose.yml with its own Postgres service and environment configuration
- [x] T035 Run full test suite (unit + integration + contract) end to end, confirm all green before marking feature complete

## Dependencies & Execution Order

- Phase 1 (Setup) blocks everything.
- Phase 2 (Foundational) blocks all user stories - do not start Phase 3/4/5 before Phase 2 checkpoint passes.
- User Stories (Phases 3, 4, 5) are independent of each other once Phase 2 is done - can be built/tested in any order, or in parallel by different contributors, since they touch different endpoints and mostly-additive service methods.
- Phase 6 (Polish) runs after all desired user stories are complete.
- Within a phase, tasks marked [P] touch different files and have no dependency on each other - safe to parallelize. Unmarked tasks in the same phase are sequential (later ones depend on earlier ones in that phase).

## Implementation Strategy

**MVP first**: Complete Phase 1 -> Phase 2 -> Phase 3 (User Story 1) only, and you have a demoable, independently-valuable slice: agents can create policy applications with proper RBAC enforcement. Stop there for a checkpoint/demo if needed.

**Incremental delivery**: Add Phase 4 (retrieval) next since it is also P1 priority, then Phase 5 (status transitions, P2) last, since it depends conceptually on policies already existing from Phase 3.
