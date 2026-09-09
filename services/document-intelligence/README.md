# Document Intelligence Service

This isolated FastAPI service provides deterministic, local document handling for claims workflows. It stores bytes and metadata in a configurable local directory, computes SHA-256 checksums, supports idempotent uploads, and never calls an external AI provider.

## Run locally

```sh
pip install -e ".[dev]"
DOCUMENT_STORAGE_PATH=./data DOCUMENT_INTELLIGENCE_API_KEY=local-development-key \
  uvicorn document_intelligence.main:app --reload
```

All non-health endpoints require `X-API-Key` (or `Authorization: Bearer ...`). The default development key is `local-development-key`; set a secret in deployed environments.

## API

- `POST /documents` (multipart `file`, optional `claim_id` and `policy_id`, optional `Idempotency-Key`)
- `GET /documents` with `q`, `claim_id`, `policy_id`, and `limit` filters
- `GET /documents/{id}` for metadata and `/content` for controlled byte retrieval
- `POST /documents/{id}/reviews` creates a rules-based, explainable pending recommendation
- `GET /documents/{id}/reviews`
- `POST /documents/reviews/{review_id}/approval` with `{"approved": true|false, "note": "..."}` for explicit human approval
- `/health` and `/readiness` are unauthenticated

Supported review indicators are intentionally small and deterministic (unsupported extension, empty content, fraud/exclusion/litigation terms, and missing signatures). A recommendation is not an approval until a human decision is recorded.

`DOCUMENT_MAX_UPLOAD_BYTES` defaults to 25 MiB. Files are stored under generated UUID names, never user-supplied paths.
