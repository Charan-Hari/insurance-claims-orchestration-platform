# Payments Integration Service

An isolated TypeScript/Node service exposing a provider-neutral payments API. It uses only Node's HTTP/crypto APIs plus `better-sqlite3` for durable, transactional idempotency records. Replace `MockPaymentProvider` in `src/provider.ts` with a real adapter without changing the HTTP boundary.

## Run locally

```sh
npm ci
npm test
npm start
```

The service listens on `PORT` (default `8080`) and stores records at `PAYMENTS_DB_PATH` (default `./data/payments.db`). The mock deterministically declines payment method tokens containing `decline`.

## API

All mutation requests require a unique `Idempotency-Key` header. Amounts are integer minor units and currencies are ISO 4217 codes.

```sh
curl -X POST http://localhost:8080/v1/payments/authorize \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: order-123' \
  -d '{"amount":1250,"currency":"USD","paymentMethodToken":"tok_local"}'
curl -X POST http://localhost:8080/v1/payments/capture \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: capture-123' \
  -d '{"amount":1250,"currency":"USD","paymentId":"PAYMENT_ID"}'
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

`X-Request-Id` is accepted or generated and returned on every response. Logs are JSON and deliberately exclude request bodies, tokens, and provider payloads.

## Wiring and deployment

This service is intentionally not added to the root Compose stack. Wire the orchestrator to `http://payments-service:8080` (or expose port 8080) and provide a persistent volume mounted at `/data` when using the Dockerfile. For production, use a managed PostgreSQL-backed store or a durable SQLite volume and run one writer instance per database.

## Development

`npm test` compiles strict TypeScript and runs Node's built-in test runner. CI is defined in `.github/workflows/payments-service-ci.yml`.
