# Copilot/RAG Service

This service provides deterministic, local, policy-aware retrieval and grounded answer
**drafts**. It uses SQLite and token-overlap ranking; it never calls an external model or
API and needs no credentials beyond the configured API key.

Every draft contains citations and the explicit disclaimer that it is not an adjudication.
Drafts start `pending` and cannot become approved without the authenticated human approval
endpoint. Approval is a workflow boundary, not an automated claim decision.

## Run locally

```sh
pip install -e ".[dev]"
$env:COPILOT_RAG_API_KEY="local-development-key"
uvicorn copilot_rag.main:app --reload --port 8006
pytest
```

Endpoints: `GET /health`, `GET /readiness`, authenticated `POST /knowledge` (or
`POST /knowledge/upload`), `GET /retrieve`, `POST /drafts`, and
`POST /drafts/{id}/approval`. Use `X-API-Key` or `Authorization: Bearer ...`.
`X-Request-ID` is echoed or generated on every response.
