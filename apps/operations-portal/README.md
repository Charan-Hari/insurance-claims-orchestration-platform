# Operations Portal

Framework-free TypeScript operations console for policy, claims, orchestration, legacy ingestion, and payments. It deliberately keeps credentials in memory (the `VITE_API_TOKEN` environment variable is injected at build time) and uses request timeouts, encoded identifiers, idempotency keys, and consistent API errors.

## Local development

```sh
npm install
npm run dev
npm test
npm run build
```

Service URLs default to ports `8000`–`8004` from the repository Compose stack. Set `VITE_API_TOKEN` for authenticated API calls. The records screen needs a policyholder UUID; the workflow screen can submit and retry an orchestration workflow. Use the reconciliation screen to inspect failed steps and retry history.

## Container

From the repository root, `docker compose up --build operations-portal` serves the compiled app at http://localhost:3000. Browser API calls still target the host service ports by default; configure `VITE_*` URLs at build time for another environment.
