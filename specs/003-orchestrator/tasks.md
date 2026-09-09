# Tasks: Orchestrator Service

## Phase 1: Setup

- [x] T001 Create `services/orchestrator` package and project metadata.
- [x] T002 Add Dockerfile and `.dockerignore`.
- [x] T003 Add test, unit, contract, and integration directories.
- [x] T004 Add health and readiness endpoints.
- [x] T005 Add structured JSON logging and request IDs.

## Phase 2: Foundation

- [x] T006 Add async database session configuration.
- [x] T007 Add Alembic configuration and initial migration.
- [x] T008 Add workflow, step, idempotency, and audit models.
- [x] T009 Add workflow schemas and state enums.
- [x] T010 Add JWT authentication and role dependencies.
- [x] T011 Add Policy Service HTTP client with timeout/retry/backoff.
- [x] T012 Add Claims Service HTTP client with timeout/retry/backoff.
- [ ] T013 Add typed downstream exceptions and safe structured logging.

## User Story 1: Start Claim Workflow

- [ ] T014 Write workflow state-transition unit tests.
- [ ] T015 Write idempotency unit and concurrency tests.
- [ ] T016 Write Policy/Claims HTTP boundary tests.
- [x] T017 Write POST workflow contract tests.
- [ ] T018 Write real-Postgres workflow creation integration tests.
- [x] T019 Implement atomic workflow and idempotency creation.
- [x] T020 Implement policy verification step.
- [x] T021 Implement claim submission step.
- [x] T022 Implement `POST /workflows/claims`.
- [ ] T023 Implement failure classification and audit events.

## User Story 2: Retrieve Workflow Status

- [ ] T024 Write workflow retrieval authorization tests.
- [ ] T025 Write GET workflow contract tests.
- [ ] T026 Write real-Postgres retrieval integration tests.
- [x] T027 Implement workflow retrieval service.
- [x] T028 Implement `GET /workflows/{workflow_id}`.

## User Story 3: Retry Failed Workflow

- [ ] T029 Write retryability and bounded-retry tests.
- [ ] T030 Write retry contract tests.
- [ ] T031 Write reconciliation-required integration tests.
- [ ] T032 Implement retry and reconciliation service logic.
- [ ] T033 Implement `POST /workflows/{workflow_id}/retry`.

## Phase 4: Polish and Integration

- [x] T034 Export the pinned OpenAPI contract.
- [x] T035 Add `services/orchestrator/README.md`.
- [x] T036 Add Orchestrator to root Docker Compose.
- [x] T037 Add Orchestrator GitHub Actions CI workflow.
- [x] T038 Run the full Orchestrator test suite.
- [x] T039 Run a live Docker Compose workflow through Policy, Claims, and
      Orchestrator.
- [ ] T040 Verify timeout, duplicate-request, retry, and reconciliation paths
      against live service boundaries.

## Completion Criteria

The Orchestrator is complete when T001-T040 are checked, all tests pass, CI is
green, and the live Compose workflow demonstrates both successful orchestration
and a non-destructive reconciliation outcome.
