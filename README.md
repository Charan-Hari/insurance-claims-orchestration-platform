# Insurance Claims Orchestration Platform

[![Policy Service CI](https://github.com/Charan-Hari/insurance-claims-orchestration-platform/actions/workflows/policy-service-ci.yml/badge.svg)](https://github.com/Charan-Hari/insurance-claims-orchestration-platform/actions/workflows/policy-service-ci.yml)
[![Claims Service CI](https://github.com/Charan-Hari/insurance-claims-orchestration-platform/actions/workflows/claims-service-ci.yml/badge.svg)](https://github.com/Charan-Hari/insurance-claims-orchestration-platform/actions/workflows/claims-service-ci.yml)

An insurance claims orchestration platform built with spec-driven development (GitHub Spec-Kit), where AI coding agents direct implementation under human review.

## Why this exists

This project demonstrates enterprise-grade delivery practices for AI-assisted engineering: specifications come before code, constitution-enforced quality gates guide implementation, and every AI-generated change is reviewed by a human before commit. State-changing policy operations also maintain an auditable trail.

## Current Status

| Service | Status | Evidence |
| --- | --- | --- |
| Policy Service | **COMPLETE** | All 3 user stories, 7 functional requirements, 21/21 tests passing, Keycloak RBAC, atomic audit trail, structured logging, Docker Compose runtime |
| Claims Service | **COMPLETE** | All 3 user stories, 8 functional requirements, 22/22 tests passing, resilient cross-service call to Policy Service (timeout+retry+backoff), atomic audit trail, structured logging, Docker Compose runtime, verified live end-to-end cross-service proof |
| Orchestrator | **IN PROGRESS** | Workflow orchestration, idempotency, retries, structured logging, Docker Compose live proof |
| Legacy Adapter | **COMPLETE** | Idempotent legacy claim ingestion, PostgreSQL persistence, Keycloak auth, health/readiness, Docker Compose |
| Payments Integration | **COMPLETE** | Provider-neutral authorize/capture/refund API, idempotency persistence, deterministic local provider, structured logs, Docker runtime |
| Document Intelligence | **COMPLETE** | Secure local document storage, checksum/idempotency, policy-aware search, explainable review, human approval workflow |
| Operations Portal | **COMPLETE** | Accessible TypeScript SPA for workflow, policy, claims, payments, legacy, audit, and reconciliation operations |
| Copilot/RAG Service | **COMPLETE** | Deterministic local policy-aware retrieval, cited answer drafts, explicit non-adjudication disclaimer, and human approval boundary |
| Platform Eventing | **AVAILABLE** | Isolated PostgreSQL transactional outbox, idempotent append, readiness, and retryable delivery abstraction |

The [Policy Service specification](specs/001-policy-service-management/) is the reference example of the complete Spec-Kit workflow, including [spec.md](specs/001-policy-service-management/spec.md), [plan.md](specs/001-policy-service-management/plan.md), [tasks.md](specs/001-policy-service-management/tasks.md), and the pinned [OpenAPI contract](specs/001-policy-service-management/contracts/policy-api.yaml).

The [Claims Service specification](specs/002-claims-service-management/) follows the same workflow and additionally demonstrates cross-service integration: [spec.md](specs/002-claims-service-management/spec.md), [plan.md](specs/002-claims-service-management/plan.md), [tasks.md](specs/002-claims-service-management/tasks.md), and the pinned [OpenAPI contract](specs/002-claims-service-management/contracts/claims-api.yaml).

## Architecture

```mermaid
flowchart LR
		UI["Operations Portal\nCOMPLETE"] --> ORCH["Orchestrator\nIN PROGRESS"]
		ORCH --> POLICY["Policy Service\nCOMPLETE"]
		ORCH --> CLAIMS["Claims Service\nCOMPLETE"]
		ORCH --> PAYMENTS["Payments Integration\nCOMPLETE"]
		LEGACY["Legacy Adapter\nCOMPLETE"] --> ORCH
		DOCS["Document Intelligence\nCOMPLETE"] --> ORCH
		COPILOT["Copilot/RAG Service\nCOMPLETE"] --> DOCS
		EVENTS["Platform Eventing\nAVAILABLE"] --> ORCH
		KEYCLOAK["Keycloak"] --> POLICY
		POLICY --> POLICYDB[(Policy PostgreSQL)]
		CLAIMS --> CLAIMSDB[(Claims DB)]

		classDef complete fill:#dcfce7,stroke:#15803d,color:#14532d
		classDef inprogress fill:#fef3c7,stroke:#d97706,color:#78350f
		classDef planned fill:#e5e7eb,stroke:#6b7280,color:#374151
		class POLICY complete
		class CLAIMS complete
		class KEYCLOAK,POLICYDB,CLAIMSDB planned
		class PAYMENTS,LEGACY complete
		class UI,DOCS,COPILOT complete
		class ORCH inprogress
```

The multi-service monorepo keeps services independently deployable while sharing one delivery process, constitution, and CI boundary.

The Platform Eventing service runs at `http://localhost:8008`; see
[services/eventing/README.md](services/eventing/README.md) for its envelope, schema,
worker adapter, and follow-up integration points.

## Quickstart

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Charan-Hari/insurance-claims-orchestration-platform?quickstart=1)

Clone the repository or open it in GitHub Codespaces, then start the local Policy Service stack:

```sh
git clone https://github.com/Charan-Hari/insurance-claims-orchestration-platform.git
cd insurance-claims-orchestration-platform
cp .env.example .env
docker compose up --build
```

The stack runs PostgreSQL 16, Keycloak in development mode, Policy Service, Claims Service, Orchestrator, Legacy Adapter, Payments Integration, Document Intelligence, Copilot/RAG, Platform Eventing, and the Operations Portal. Each Python service applies Alembic migrations before starting Uvicorn; local SQLite services use persistent volumes. For full Keycloak realm, client, and JWT setup, see [services/policy/README.md](services/policy/README.md).

With a valid Keycloak token in `TOKEN`, the three primary policy operations are:

```sh
# Create a policy application
curl -X POST http://localhost:8000/policies \
	-H "Authorization: Bearer $TOKEN" \
	-H 'Content-Type: application/json' \
	-d '{"policyholder_id":"11111111-1111-1111-1111-111111111111","coverage_type":"property","coverage_limits":{"dwelling":250000},"effective_date":"2026-10-01","expiry_date":"2027-10-01","premium_amount":"1200.00"}'

# Retrieve a policy
curl http://localhost:8000/policies/POLICY_ID \
	-H "Authorization: Bearer $TOKEN"

# Transition a policy status with an underwriter or admin token
curl -X PATCH http://localhost:8000/policies/POLICY_ID/status \
	-H "Authorization: Bearer $TOKEN" \
	-H 'Content-Type: application/json' \
	-d '{"status":"pending_underwriting"}'
```

## Delivery Process

Feature work follows the Spec-Kit workflow: **constitution -> specify -> clarify -> plan -> tasks -> implement**, with tests and review gates around implementation. Read the [project constitution](.specify/memory/constitution.md) for the security, audit, resilience, integration, and human-review requirements.

Every AI-generated change was reviewed before commit. The [commit history](https://github.com/Charan-Hari/insurance-claims-orchestration-platform/commits/main/) contains the implementation sequence and detailed rationale in the commit messages.

## Tech Stack

| Service | Language | Framework / Runtime | Data / Integration | Status |
| --- | --- | --- | --- | --- |
| Policy Service | Python 3.12 | FastAPI, SQLAlchemy 2.0 async, Alembic | PostgreSQL 16, Keycloak | Complete |
| Claims Service | Python 3.12 | FastAPI, SQLAlchemy 2.0 async, Alembic | PostgreSQL 16, Keycloak, live HTTP call to Policy Service | Complete |
| Orchestrator | Python 3.12 | FastAPI | PostgreSQL, Policy and Claims APIs, saga coordination | In progress |
| Legacy Adapter | Python 3.12 | FastAPI, SQLAlchemy 2.0 async, Alembic | PostgreSQL, Keycloak, legacy claim feeds | Complete |
| Payments Integration | TypeScript | Node.js HTTP service | Provider-neutral payment API, SQLite idempotency store | Complete |
| Document Intelligence | Python 3.12 | FastAPI | Local document storage, SQLite metadata, deterministic review rules | Complete |
| Operations Portal | TypeScript | Vite SPA | Policy, Claims, Orchestrator, Legacy, Payments, and Document APIs | Complete |
| Copilot/RAG Service | Python 3.12 | FastAPI, deterministic token retrieval | SQLite local knowledge store | Complete |
| Platform Eventing | Python 3.12 | FastAPI, SQLAlchemy async, outbox worker | PostgreSQL transactional outbox, publisher adapter | Available |

## Demo

TODO: Add a recorded terminal walkthrough using asciinema or a GIF showing the Compose stack, Keycloak JWT flow, policy lifecycle, and audit record.

## License

This project is licensed under the [MIT License](LICENSE).