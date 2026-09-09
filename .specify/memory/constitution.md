# Insurance Claims Orchestration Platform Constitution

## Core Principles

### I. Security-First
All external inputs (API requests, uploaded documents, webhook payloads) MUST be validated
against an explicit schema before processing. Secrets (API keys, database credentials,
signing keys) MUST NEVER be hardcoded or committed to source control; they are supplied via
environment variables or a secrets manager. Every endpoint MUST enforce role-based access
control (RBAC) — there are no unauthenticated internal endpoints. Authentication and
authorization are handled via Keycloak (OIDC/RBAC), not custom-rolled auth.

### II. Audit-First
Every state-changing operation on a policy, claim, or payment MUST write an immutable,
append-only audit record (who, what, when, before/after state, correlation ID). Audit
records are never updated or deleted, only appended. Audit trails must be queryable
independently of the services that produced them, so compliance reviews do not depend on
service uptime.

### III. Resilience (Compensating Actions, Not Silent Inconsistency)
Cross-service workflows (sagas) MUST define an explicit compensating action for every step
that has side effects (e.g., a payment that succeeds but a downstream policy update that
fails MUST trigger a refund/rollback step). Partial failure must never leave the system in
an undetected inconsistent state — every saga step failure is logged, alertable, and either
auto-compensated or escalated for manual review. A reconciliation job periodically checks for
drift between services and flags it.

### IV. Contract-Driven Integration
Services communicate through versioned, documented APIs (OpenAPI specs checked into the
repo). Breaking changes require a new API version, not an in-place change. External
integrations (Stripe, Keycloak, any legacy feed) are isolated behind a dedicated adapter/
integration service — no domain service calls an external API directly. Contract tests
verify that a service's actual behavior matches its published contract before merge.

### V. Test-Verified Delivery (NON-NEGOTIABLE)
No feature is considered done unless its acceptance criteria (defined in the feature's
Spec-Kit spec.md) are each covered by at least one passing automated test. Coverage must
not regress from the baseline on any change. CI blocks merge if tests fail, coverage drops,
or a security scan reports a new high/critical finding.

### VI. Polyglot by Design, Bounded by Purpose
Python is used for domain and orchestration services (Policy, Claims, Orchestrator, Legacy
Adapter, Copilot). TypeScript is used for the Payments integration service and the Angular
frontend. Each service owns its own datastore/schema; no service reaches into another
service's database directly — all cross-service access goes through its published API.

## Delivery Process Requirements

Every feature MUST follow the Spec-Kit workflow before implementation begins:
constitution -> specify -> clarify -> plan -> checklist -> tasks -> analyze -> implement ->
converge. Specs are written and committed before the corresponding code. Every PR must
reference the spec/feature it implements. CI Guard and Architecture Guard checks must pass
before merge. Delivery metrics (cycle time from spec commit to merge, rework rate, coverage
trend) are collected for every feature and reviewed periodically.

## Review & Quality Gates

All AI-agent-generated code is reviewed by a human before merge — no auto-merge on agent
output. Reviewers explicitly check: does the implementation satisfy the spec's acceptance
criteria; are secrets/PII handled correctly; is the audit trail written for every
state-changing operation; are compensating actions defined for every saga step with side
effects. Findings from review are logged, not just fixed silently, so the delivery-metrics
layer can track rework rate.

## Governance

This constitution supersedes ad hoc practices. Amendments require a documented rationale and
must be reflected in .specify/memory/constitution.md with an updated version and amendment
date. All specs, plans, and PRs are evaluated against these principles; deviations must be
explicitly justified in the plan's "Complexity Tracking" section.

**Version**: 1.0.0 | **Ratified**: 2026-09-06 | **Last Amended**: 2026-09-06
