# Feature Specification: Claims Service Management

**Feature Branch**: `002-claims-service-management`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: Build a Claims Service that manages the insurance claim lifecycle. It must support: filing a new claim against an existing active policy (claim amount, incident date, description), retrieving a claim by ID, listing claims for a policyholder, updating claim status through a defined lifecycle (submitted -> under_review -> approved -> paid; submitted -> under_review -> denied; under_review -> closed), and recording the claim amount and adjuster notes. Every state transition must write an immutable audit record. Access must be role-scoped: agents and adjusters can create/update claims; customers can only view their own claims; admins have full access. A claim may only be filed against a policy that is currently in 'active' status, verified via a call to the Policy Service.

## User Scenarios & Testing

### User Story 1 - File a Claim (Priority: P1)

As an agent, I want to file a new claim against a policyholder's active policy, so that the claims review process can begin.

**Why this priority**: Core functionality needed to start the claims lifecycle.

**Independent Test**: Agent files a claim referencing an active policy ID with incident date, description, and claimed amount. Claim is persisted in 'submitted' status.

**Acceptance Scenarios**:

1. **Given** an agent is logged in and the referenced policy is 'active', **When** they file a new claim with valid details, **Then** the system saves the claim in 'submitted' status.
2. **Given** an agent is logged in and the referenced policy is NOT 'active' (e.g. draft, cancelled, expired), **When** they attempt to file a claim, **Then** the system rejects the request with a validation error.
3. **Given** a customer is logged in, **When** they attempt to file a claim, **Then** the system denies the action.

---

### User Story 2 - Retrieve Claim (Priority: P1)

As a customer, I want to retrieve details of my claim, so that I can track its progress.

**Why this priority**: Essential for customer transparency into claims status.

**Independent Test**: Customer retrieves their own claim by ID.

**Acceptance Scenarios**:

1. **Given** a customer is logged in, **When** they retrieve their own claim by ID, **Then** the system displays the claim details.
2. **Given** a customer is logged in, **When** they attempt to retrieve another policyholder's claim by ID, **Then** the system denies access (returns not-found, to avoid leaking existence).
3. **Given** an admin, agent, or adjuster is logged in, **When** they retrieve any claim, **Then** the system displays the claim details.

---

### User Story 3 - Update Claim Status (Priority: P2)

As an adjuster, I want to update a claim's status as it moves through review, so that it progresses toward resolution (approved/denied/paid/closed).

**Why this priority**: Enables the core claims review workflow.

**Independent Test**: Adjuster updates status of a claim. Audit log records the transition.

**Acceptance Scenarios**:

1. **Given** a claim is in 'submitted' status, **When** an adjuster updates status to 'under_review', **Then** the system updates status and creates an immutable audit record of the transition.
2. **Given** a claim, **When** a customer attempts to update its status, **Then** the system denies the action.
3. **Given** a claim is in 'under_review' status, **When** an adjuster attempts an invalid transition (e.g. directly to 'paid'), **Then** the system rejects it with a validation error and no state change occurs.

---

### Edge Cases

- What happens if the Policy Service is unreachable when filing a new claim (policy-status verification call fails)?
- How does the system handle an invalid status transition?
- How does the system ensure atomicity of status update and audit log creation?
- What happens if the referenced policy ID does not exist at all?

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow agents and adjusters to file a new claim against an existing policy.
- **FR-002**: System MUST verify, via a call to the Policy Service, that the referenced policy exists and is currently in 'active' status before allowing claim creation.
- **FR-003**: System MUST allow retrieval of a claim by its unique ID.
- **FR-004**: System MUST allow listing all claims belonging to a specific policyholder.
- **FR-005**: System MUST support status lifecycle: submitted -> under_review -> (approved -> paid) | denied | closed.
- **FR-006**: System MUST allow recording of the claim amount, incident date, description, and adjuster notes.
- **FR-007**: System MUST create an immutable audit record for every state transition, capturing the actor, old status, new status, and timestamp.
- **FR-008**: System MUST enforce role-scoped access:
    - Agents/Adjusters: Can create/update claims.
    - Customers: Can view only their own claims.
    - Admins: Can view/update all claims.

### Key Entities

- **Claim**: Unique ID, Policy ID (reference), Policyholder ID, Claim Amount, Incident Date, Description, Adjuster Notes, Current Status, Created/Updated timestamps.
- **AuditRecord**: Claim ID, Actor ID, Old Status, New Status, Timestamp.

## Success Criteria

### Measurable Outcomes

- **SC-001**: System records state transition and audit log in a single atomic transaction.
- **SC-002**: Unauthorized access attempts are blocked with a clear denial response; customer attempts to view another policyholder's claim return not-found rather than forbidden.
- **SC-003**: Claim creation correctly rejects any policy not in 'active' status, verified via a live Policy Service call.
- **SC-004**: Average time to retrieve claim details is under 500ms.

## Assumptions

- Audit logs cannot be deleted or modified once created.
- The Policy Service exposes an accessible endpoint to check policy status by ID (GET /policies/{id}), reused for this cross-service check.
- Policyholder identity is uniquely identified within the system and consistent between Policy Service and Claims Service (same policyholder_id / JWT subject convention as Policy Service).
- Access control mechanisms (RBAC) are available for role validation, using the same Keycloak realm/roles as Policy Service.

## Clarifications

### Session 2026-09-07

- **Q: What happens if the Policy Service is unreachable when filing a new claim?**
  A: The system MUST reject the claim creation request with a 503-equivalent
  "dependency unavailable" error rather than allowing the claim to be created
  unverified. No claim record or audit record is created. The caller may retry.

- **Q: How does the system handle an invalid status transition?**
  A: The system MUST reject the transition and return a validation error identifying
  the current status and the invalid target status. No state change occurs, and no
  audit record is written for a rejected transition attempt. Valid transitions are
  strictly: submitted -> under_review; under_review -> approved; under_review -> denied;
  under_review -> closed; approved -> paid. Any transition not in this list is invalid.

- **Q: How does the system ensure atomicity of status update and audit log creation?**
  A: The claim status update and its corresponding audit record MUST be written within
  a single database transaction, identical to the approach used in the Policy Service.
  If the audit record write fails for any reason, the entire transaction MUST roll back,
  leaving the claim's status unchanged.

- **Q: What happens if the referenced policy ID does not exist at all?**
  A: The system MUST reject claim creation with a validation error indicating the
  policy was not found. This is distinguished internally from the "policy not active"
  case for logging purposes, but both return a 400-equivalent validation error to the
  caller (not a 404, since the claim resource itself was never being addressed).

### Updated Edge Cases (resolved)

- Policy Service unavailable: claim creation rejected with a dependency-unavailable error; no partial state persisted (see Clarifications above).
- Invalid status transitions are rejected with a validation error; no partial state change occurs (see Clarifications above).
- Status update and audit record creation are atomic via a single database transaction (see Clarifications above).
- Non-existent policy ID: claim creation rejected with a validation error (see Clarifications above).

## Amendment: Idempotent Claim Creation

To support reliable orchestration and safe retry after ambiguous responses,
`POST /claims` must accept an `Idempotency-Key` request header.

- The key is required for orchestrated claim creation.
- The key must be scoped to the authenticated caller.
- The key and claim creation must be persisted atomically.
- Repeating the same key with the same request returns the original claim.
- Repeating the same key with a different request returns `409 Conflict`.
- A failed transaction must not reserve the key.
- The idempotency record must store a request fingerprint and resulting claim ID.
- Authorization tokens must never be stored or logged.
