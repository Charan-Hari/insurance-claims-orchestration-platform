# Copilot/RAG Service

Policy-aware retrieval and grounded answer **drafts** for claim handlers, with human
approval as a hard boundary.

The service defaults to a **deterministic, fully offline** generator so the platform runs
with no API key, no account, and no per-request cost. A hosted large language model is
opt-in via a single environment variable.

## Why it is provider-agnostic

Free-tier hosted APIs commonly reserve the right to use submitted content for model
training, which is the wrong default for claim data. Making the hosted provider opt-in
keeps the default path entirely on-box, keeps CI hermetic, and lets anyone clone the repo
and get working behaviour immediately.

Two properties hold regardless of which generator is active:

- **Grounded or refused.** Answers use only the retrieved, policy-scoped passages. When
  retrieval returns nothing, the generator refuses rather than inferring.
- **Never auto-approved.** Drafts are created `pending` and require the authenticated
  human approval endpoint. Approval is a workflow boundary, not an automated decision.

Because approval is mandatory, a provider outage is a quality concern rather than a
safety one, so hosted failures **degrade to the deterministic generator** instead of
failing the request. Every draft records which generator produced it:

```json
{ "generator": "deterministic", "degraded": true, "degraded_reason": "HTTPStatusError: ... 429" }
```

Degradation is therefore visible to operators and auditable after the fact, never silent.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COPILOT_LLM_PROVIDER` | `deterministic` | `deterministic`, `gemini`, or `openai` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | – | Key for the selected provider |
| `COPILOT_LLM_MODEL` | provider default | Override the model |
| `COPILOT_LLM_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `COPILOT_RAG_API_KEY` | `local-development-key` | Caller authentication |
| `COPILOT_RAG_DB_PATH` | `/var/lib/copilot-rag/copilot-rag.db` | SQLite location |

An unset key or unknown provider falls back to the deterministic generator rather than
preventing startup. **Never commit an API key**; supply it through the environment.

### Enabling a hosted model

```sh
export COPILOT_LLM_PROVIDER=gemini
export GEMINI_API_KEY=...   # from Google AI Studio
```

## Retrieval

Ranking is token-overlap over SQLite, filtered by `policy_id`/`claim_id`. It is
deliberately simple and dependency-free; the extension point that matters for this
service is generation and its governance, not the scoring function.

## Run locally

```sh
pip install -e ".[dev]"
export COPILOT_RAG_API_KEY=local-development-key
uvicorn copilot_rag.main:app --reload --port 8006
pytest
```

Endpoints: `GET /health`, `GET /readiness`, and authenticated `POST /knowledge`
(or `POST /knowledge/upload`), `GET /retrieve`, `POST /drafts`,
`POST /drafts/{id}/approval`. Authenticate with `X-API-Key` or `Authorization: Bearer`.
`X-Request-ID` is echoed or generated on every response.

Tests cover both generators, the request shape sent to each provider, refusal on empty
retrieval, and the degradation path — all without network access or credentials.
