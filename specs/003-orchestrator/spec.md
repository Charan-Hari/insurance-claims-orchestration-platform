# Orchestrator Service

## Purpose

Coordinate cross-service insurance workflows without allowing direct database
access between services. The Orchestrator owns workflow state, idempotency,
timeouts, retry policy, and operational audit events.

## User Story 1: Start a Claim Workflow

As an operations user, I can start a claim workflow for a policy so that the
system verifies the policy and creates the claim through the Claims Service.

### Acceptance Criteria

- The API accepts a client-supplied idempotency key.
- Duplicate requests with the same idempotency key return the original workflow.
- The Orchestrator calls Policy Service to retrieve the policy.
- A policy must be `active`; otherwise the workflow fails without creating a claim.
- The Orchestrator calls Claims Service using the caller's authorization context.
- The workflow records each step transition and outcome.
- A successful workflow returns `completed` and the created claim ID.
- Policy Service timeout/unavailability produces a retryable workflow failure.
- Claims Service timeout/unavailability produces a retryable workflow failure.
- Authorization headers and tokens are never written to logs or audit records.

## User Story 2: Retrieve Workflow Status

As an operations user, I can retrieve workflow status so that I can monitor
in-progress, completed, and failed orchestration attempts.

### Acceptance Criteria

- The API returns workflow state, step states, timestamps, failure category,
  and claim ID when available.
- Customers can retrieve only workflows for their own policyholder ID.
- Agents, adjusters, and admins can retrieve workflows they are authorized to
  operate.
- Unknown workflow IDs return `404`.
- Workflow status reads do not mutate workflow state.

## User Story 3: Retry a Failed Workflow

As an operations user, I can retry a retryable failed workflow without creating
duplicate claims.

### Acceptance Criteria

- Only retryable failures can be retried.
- The retry uses the original idempotency key.
- A completed workflow is returned unchanged when retried.
- Non-retryable failures are not retried.
- Retry attempts and outcomes are recorded in the workflow audit trail.
- Retry count is bounded.

## Workflow States

- `pending`
- `policy_verified`
- `claim_submitted`
- `completed`
- `failed`
- `reconciliation_required`

## Step States

- `pending`
- `running`
- `succeeded`
- `failed`
- `skipped`

## Failure and Compensation Rules

- Policy verification failure prevents claim creation.
- Claims Service failure after successful policy verification marks the workflow
  failed and does not mutate the policy.
- If claim creation succeeds but the response is lost, the Orchestrator retries
  with the same idempotency key and reconciles the existing result.
- The Orchestrator must not delete or directly modify Claims or Policy database
  records.
- If a downstream result cannot be reconciled, the workflow becomes
  `reconciliation_required` and records an operational alert event.

## Functional Requirements

- FR-001: Provide `POST /workflows/claims`.
- FR-002: Provide `GET /workflows/{workflow_id}`.
- FR-003: Provide `POST /workflows/{workflow_id}/retry`.
- FR-004: Persist workflow state independently from Policy and Claims databases.
- FR-005: Enforce idempotency for workflow creation and retry.
- FR-006: Use bounded timeout, retry, and backoff policies for service calls.
- FR-007: Persist an audit event for every workflow and step transition.
- FR-008: Propagate authorization context without logging credentials.
- FR-009: Enforce customer ownership and elevated-role authorization.
- FR-010: Expose structured health and readiness endpoints.

## Non-Goals

- Direct database access to Policy or Claims databases.
- Replacing Policy Service or Claims Service business rules.
- Destructive compensation such as deleting claims.
- Payment processing.
- User-interface implementation.

## Required Verification

- Unit tests for state transitions and idempotency.
- Contract tests for all workflow endpoints.
- Integration tests using real PostgreSQL.
- HTTP boundary tests for Policy and Claims dependencies.
- Failure-path tests for timeout, retry exhaustion, duplicate requests,
  lost responses, and reconciliation-required outcomes.
- Docker Compose verification with Policy, Claims, and Orchestrator services.
