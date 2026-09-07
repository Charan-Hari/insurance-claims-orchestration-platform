# Tasks: Claims Service Management

**Input**: Design documents from specs/002-claims-service-management/
**Prerequisites**: plan.md, spec.md

**Tests**: Tests are included for every functional requirement per constitution
Principle V (Test-Verified Delivery). Test tasks are written before their
corresponding implementation tasks.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested, and demoed independently. [P] marks a task that can run
in parallel with other [P] tasks in the same phase (different files, no
shared dependency).

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create services/claims/ directory skeleton (src/claims_service/{api,models,schemas,services,auth,db}, tests/{unit,integration,contract}) per plan.md Project Structure
- [ ] T002 Create services/claims/pyproject.toml with dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, python-jose[cryptography], pydantic, httpx, and a [dev] extras group with pytest, pytest-asyncio, testcontainers, respx (for mocking the Policy Service HTTP client in tests)
- [ ] T003 [P] Create services/claims/Dockerfile (python:3.12-slim base, copy pyproject.toml + alembic.ini + src, install deps, run uvicorn) - reuse the corrected pattern from services/policy/Dockerfile (must include alembic.ini)
- [ ] T004 [P] Create services/claims/alembic.ini and services/claims/src/claims_service/db/migrations/ scaffold, using the corrected async env.py pattern from services/policy (connection.run_sync(do_run_migrations), not context.run_migrations() directly)
- [ ] T005 [P] Create services/claims/src/claims_service/db/session.py with async SQLAlchemy engine/session factory reading DATABASE_URL from environment
- [ ] T006 [P] Create services/claims/src/claims_service/auth/jwt.py: copy the Policy Service's JWT validation implementation (issuer/JWKS validation with 10-minute cache keyed by issuer, kid-rotation aware), same KEYCLOAK_ISSUER/KEYCLOAK_AUDIENCE environment variable convention
- [ ] T007 Create services/claims/src/claims_service/main.py: FastAPI app instance, health/readiness endpoints, JSON structured logging middleware (reuse services/policy/src/policy_service/logging_config.py pattern), router registration

**Checkpoint**: Service skeleton runs (`uvicorn` boots), health check returns 200. No business logic yet.

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T008 Create services/claims/src/claims_service/models/claim.py: Claim ORM model (id, policy_id, policyholder_id, claim_amount, incident_date, description, adjuster_notes, status, created_at, updated_at)
- [ ] T009 Create services/claims/src/claims_service/models/audit.py: AuditRecord ORM model (id, claim_id FK, actor_id, old_status, new_status, created_at) - no update/delete methods exposed
- [ ] T010 Generate initial Alembic migration for claim and audit_record tables in services/claims/src/claims_service/db/migrations/versions/ (verify the revision ID length is within Alembic's default 32-char version column, per the issue found in the Policy Service)
- [ ] T011 Create services/claims/src/claims_service/schemas/claim.py: Pydantic schemas (ClaimCreate, ClaimRead, ClaimStatusUpdate, AuditRecordRead), with validation that claim_amount is non-negative and incident_date is not in the future
- [ ] T012 Define the claim status transition state machine (VALID_STATUS_TRANSITIONS map per spec Clarifications: submitted->under_review, under_review->approved, under_review->denied, under_review->closed, approved->paid) in services/claims/src/claims_service/services/claim_service.py
- [ ] T013 Create services/claims/src/claims_service/services/policy_client.py: httpx-based client with a get_policy(policy_id) function that calls the Policy Service's GET /policies/{id}, using a 2s per-attempt timeout and up to 2 retries with exponential backoff (total budget ~5s). Define typed exceptions: PolicyNotFound (404 response), PolicyServiceUnavailable (timeout/connection error after retries exhausted). Read POLICY_SERVICE_BASE_URL from environment. Do not log the JWT/Authorization header used for the internal call.

**Checkpoint**: DB schema exists, migrations apply cleanly against a local Postgres container. policy_client.py is unit-testable in isolation (mocked). No endpoints wired yet.

## Phase 3: User Story 1 - File a Claim (Priority: P1)

**Goal**: Agent/adjuster can file a claim against an active policy, persisted in 'submitted' status. Customers are denied. Non-active or non-existent policies are rejected. Policy Service unavailability is handled gracefully.

**Independent Test**: POST a valid claim payload (referencing an active policy) as an agent -> 201 with status=submitted. POST as a customer -> 403. POST referencing a non-active policy -> 400. POST when Policy Service is unreachable -> 503.

- [ ] T014 [P] [US1] Unit test: services/claims/tests/unit/test_claim_service_create.py - validates submitted status default, rejects missing required fields, rejects negative claim_amount or future incident_date
- [ ] T015 [P] [US1] Unit test: services/claims/tests/unit/test_policy_client.py - using respx to mock httpx responses: 200 active policy -> success, 200 non-active policy -> PolicyNotActive-equivalent handling, 404 -> PolicyNotFound, timeout/connection error after retries -> PolicyServiceUnavailable
- [ ] T016 [P] [US1] Contract test: services/claims/tests/contract/test_create_claim_contract.py - validates request/response shape against contracts/claims-api.yaml
- [ ] T017 [US1] Integration test: services/claims/tests/integration/test_create_claim.py - agent creates claim against a mocked-active policy (201, submitted), customer attempt denied (403), claim against a mocked-non-active policy rejected (400), claim when Policy Service mock returns connection error rejected (503), using testcontainers Postgres + mocked policy_client
- [ ] T018 [US1] Implement create_claim business logic in services/claims/src/claims_service/services/claim_service.py, calling policy_client.get_policy() before persisting, translating PolicyNotFound/policy-not-active into a 400-equivalent validation error and PolicyServiceUnavailable into a 503-equivalent error
- [ ] T019 [US1] Implement POST /claims endpoint in services/claims/src/claims_service/api/routes.py with role dependency (agent, adjuster only), mapping service-layer exceptions to the correct HTTP status codes
- [ ] T020 [US1] Run tests T014-T017, confirm green

**Checkpoint**: User Story 1 fully working and independently testable/demoable, including the cross-service resilience behavior.

## Phase 4: User Story 2 - Retrieve Claim (Priority: P1)

**Goal**: Customers view only their own claim (matched via policyholder_id); admins/agents/adjusters view any claim; listing by policyholder works. Unauthorized customer access returns 404 (not 403), consistent with the Policy Service's existence-leak fix.

**Independent Test**: Customer GETs own claim -> 200. Customer GETs another's claim -> 404. Admin/agent/adjuster GETs any claim -> 200.

- [ ] T021 [P] [US2] Unit test: services/claims/tests/unit/test_claim_service_get.py - ownership check logic
- [ ] T022 [P] [US2] Contract test: services/claims/tests/contract/test_get_claim_contract.py
- [ ] T023 [US2] Integration test: services/claims/tests/integration/test_get_claim.py - own/other/admin/agent/adjuster access scenarios, missing claim -> 404, another policyholder's existing claim -> 404 (not 403)
- [ ] T024 [US2] Implement get_claim_by_id and list_claims_for_policyholder in services/claims/src/claims_service/services/claim_service.py with ownership/role enforcement (reuse the can_view_policy/can_view_policyholder pattern from Policy Service, renamed for claims)
- [ ] T025 [US2] Implement GET /claims/{id} and GET /policyholders/{id}/claims endpoints in services/claims/src/claims_service/api/routes.py
- [ ] T026 [US2] Run tests T021-T023, confirm green

**Checkpoint**: User Stories 1 and 2 both working independently. Retrieval performance (SC-004, p95 < 500ms) spot-checked.

## Phase 5: User Story 3 - Update Claim Status (Priority: P2)

**Goal**: Adjuster transitions claim status; every transition writes an immutable audit record atomically; invalid transitions rejected; customers denied.

**Independent Test**: Adjuster transitions submitted -> under_review -> 200 + audit row created. Invalid transition (submitted -> paid directly) -> 400, no audit row, no status change. Customer attempt -> 403.

- [ ] T027 [P] [US3] Unit test: services/claims/tests/unit/test_status_transitions.py - valid/invalid transition matrix per spec Clarifications
- [ ] T028 [P] [US3] Contract test: services/claims/tests/contract/test_update_status_contract.py
- [ ] T029 [US3] Integration test: services/claims/tests/integration/test_update_claim_status.py - valid transition + audit row atomicity, invalid transition rejected with no partial state, customer denied, and explicit verification that zero audit rows exist after a rejected invalid transition
- [ ] T030 [US3] Implement update_claim_status in services/claims/src/claims_service/services/claim_service.py: single DB transaction wrapping status update + audit insert, rollback both on any failure (reuse the exact pattern from Policy Service's update_policy_status)
- [ ] T031 [US3] Implement PATCH /claims/{id}/status endpoint in services/claims/src/claims_service/api/routes.py with role dependency (adjuster, admin only)
- [ ] T032 [US3] Run tests T027-T029, confirm green, explicitly verify no audit row exists after a rejected invalid transition

**Checkpoint**: All three user stories complete and independently testable. Full FR-001 through FR-008 coverage achieved.

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Export OpenAPI schema from the running service to contracts/claims-api.yaml, commit as the pinned contract artifact
- [ ] T034 [P] Add structured JSON logging to all endpoints (reuse Policy Service's logging_config.py pattern), including an explicit log line for policy_client calls (target service, outcome, latency) without logging the Authorization header
- [ ] T035 [P] Write services/claims/README.md: local run instructions, environment variables required (including POLICY_SERVICE_BASE_URL), how to run tests, troubleshooting section
- [ ] T036 Add services/claims to root docker-compose.yml with its own Postgres database (claims_db) and POLICY_SERVICE_BASE_URL pointing at the policy-service container; add a healthcheck for claims-service
- [ ] T037 Add a GitHub Actions workflow at .github/workflows/claims-service-ci.yml mirroring policy-service-ci.yml (path-filtered to services/claims/**, installs [dev] extras, runs full pytest suite including testcontainers integration tests)
- [ ] T038 Run the full test suite (unit + integration + contract) end to end, confirm all green, and verify docker compose up brings up postgres/keycloak/policy-service/claims-service all healthy, with a live curl test: file a claim via claims-service referencing a policy created via policy-service, confirming the real cross-service call succeeds

## Dependencies & Execution Order

- Phase 1 (Setup) blocks everything.
- Phase 2 (Foundational) blocks all user stories - do not start Phase 3/4/5 before Phase 2 checkpoint passes. Note T013 (policy_client.py) is foundational since User Story 1 depends on it directly.
- User Stories (Phases 3, 4, 5) are independent of each other once Phase 2 is done, EXCEPT that Phase 3 (Create) naturally needs to run before Phase 4/5 can be meaningfully demoed end-to-end (a claim must exist before it can be retrieved or transitioned), even though the code itself has no hard dependency.
- Phase 6 (Polish) runs after all desired user stories are complete, and includes the real cross-service integration proof (T038) which requires both Policy Service and Claims Service running together.

## Implementation Strategy

**MVP first**: Complete Phase 1 -> Phase 2 -> Phase 3 (User Story 1) only, and you have a demoable, independently-valuable slice: agents can file claims against verified active policies, with real resilience handling for the Policy Service dependency.

**Incremental delivery**: Add Phase 4 (retrieval) next since it is also P1 priority, then Phase 5 (status transitions, P2) last.

**Key difference from Policy Service delivery**: this feature's most interesting/differentiating work is the policy_client.py resilience logic (T013, T015) and the final end-to-end cross-service proof (T038) - prioritize getting those right over polish tasks if time is constrained.
