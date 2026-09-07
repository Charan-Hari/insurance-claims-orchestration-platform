# Feature Specification: Policy Service Management

**Feature Branch**: `001-policy-service-management`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: Build a Policy Service that manages insurance policy lifecycle for a property & casualty carrier. It must support: creating a new policy application (policyholder details, coverage type, coverage limits, effective/expiry dates), retrieving a policy by ID, listing policies for a policyholder, updating policy status through a defined lifecycle (draft -> pending_underwriting -> active -> cancelled -> expired -> renewed), and recording premium amount. Every state transition must write an immutable audit record. Access must be role-scoped: only agents and underwriters can create/update policies; customers can only view their own policies; admins have full access.

## User Scenarios & Testing

### User Story 1 - Create Policy Application (Priority: P1)

As an agent, I want to create a new policy application, so that I can initiate the underwriting process for a prospective client.

**Why this priority**: Core functionality needed to start the lifecycle.

**Independent Test**: Agent creates an application with policyholder details, coverage type, limits, and dates. Application is persisted in 'draft' state.

**Acceptance Scenarios**:

1. **Given** an agent is logged in, **When** they create a new policy application with valid details, **Then** the system saves the application in 'draft' status.
2. **Given** a customer is logged in, **When** they attempt to create a policy application, **Then** the system denies the action.

---

### User Story 2 - Retrieve Policy (Priority: P1)

As a customer, I want to retrieve details of my policy, so that I can view my coverage.

**Why this priority**: Essential for customer transparency.

**Independent Test**: Customer retrieves their own policy by ID.

**Acceptance Scenarios**:

1. **Given** a customer is logged in, **When** they retrieve their own policy by ID, **Then** the system displays the policy details.
2. **Given** a customer is logged in, **When** they attempt to retrieve another customer's policy by ID, **Then** the system denies access.
3. **Given** an admin is logged in, **When** they retrieve any policy, **Then** the system displays the policy details.

---

### User Story 3 - Update Policy Status (Priority: P2)

As an underwriter, I want to update the policy status, so that I can progress the policy through its lifecycle (e.g., from 'draft' to 'pending_underwriting').

**Why this priority**: Enables policy lifecycle management.

**Independent Test**: Underwriter updates status of a policy. Audit log records the transition.

**Acceptance Scenarios**:

1. **Given** a policy is in 'draft' status, **When** an underwriter updates status to 'pending_underwriting', **Then** the system updates status and creates an immutable audit record of the transition.
2. **Given** a policy, **When** a customer attempts to update its status, **Then** the system denies the action.

---

### Edge Cases

- How does the system handle an invalid status transition (e.g., 'active' -> 'draft')?
- How does the system ensure atomicity of status update and audit log creation?

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow agents and underwriters to create a new policy application.
- **FR-002**: System MUST allow retrieval of a policy by its unique ID.
- **FR-003**: System MUST allow listing all policies belonging to a specific policyholder.
- **FR-004**: System MUST support status lifecycle: draft -> pending_underwriting -> active -> cancelled -> expired -> renewed.
- **FR-005**: System MUST allow recording of the premium amount for a policy.
- **FR-006**: System MUST create an immutable audit record for every state transition, capturing the actor, old status, new status, and timestamp.
- **FR-007**: System MUST enforce role-scoped access:
    - Agents/Underwriters: Can create/update policies.
    - Customers: Can view only their own policies.
    - Admins: Can view/update all policies.

### Key Entities

- **Policy**: Unique ID, Policyholder ID, Coverage Type, Coverage Limits, Effective Date, Expiry Date, Current Status, Premium Amount.
- **AuditRecord**: Policy ID, Actor ID, Old Status, New Status, Timestamp.

## Success Criteria

### Measurable Outcomes

- **SC-001**: System records state transition and audit log in a single atomic transaction.
- **SC-002**: Unauthorized access attempts (e.g., customer trying to update status) are blocked with a clear 'access denied' response.
- **SC-003**: Average time to retrieve policy details is under 500ms.

## Assumptions

- Audit logs cannot be deleted or modified once created.
- Policyholder identity is uniquely identified within the system.
- Access control mechanisms (RBAC) are available for role validation.

## Clarifications

### Session 2026-09-06

- **Q: How does the system handle an invalid status transition (e.g., 'active' -> 'draft')?**
  A: The system MUST reject the transition and return a validation error identifying the
  current status and the invalid target status. No state change occurs, and no audit
  record is written for a rejected transition attempt. Valid transitions are strictly:
  draft -> pending_underwriting -> active -> cancelled; active -> expired; active/expired
  -> renewed; renewed -> pending_underwriting (re-underwriting cycle). Any transition not
  in this list is invalid.

- **Q: How does the system ensure atomicity of status update and audit log creation?**
  A: The policy status update and its corresponding audit record MUST be written within a
  single database transaction. If the audit record write fails for any reason, the entire
  transaction MUST roll back, leaving the policy's status unchanged. Callers must never
  observe a state where the policy status changed but no audit record exists for that
  change, or vice versa.

### Updated Edge Cases (resolved)

- Invalid status transitions are rejected with a validation error; no partial state change occurs (see Clarifications above).
- Status update and audit record creation are atomic via a single database transaction (see Clarifications above).
